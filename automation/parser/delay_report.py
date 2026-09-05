from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterable, Mapping
from collections import Counter

from .workbook import read_workbook_sheets


TOLERANCE_MINUTES = 10
REQUIRED_HEADERS = {
    "Nome",
    "Data",
    "Turno",
    "Primeiro ponto previsto",
    "Primeiro ponto realizado",
    "Tempo de atraso",
}


@dataclass(frozen=True, slots=True)
class DelayBand:
    label: str
    minimum_minutes: int
    maximum_minutes: int | None
    color: str


DELAY_BANDS = {
    "TOLERANCIA": DelayBand("Dentro da tolerância", 0, 10, "#1976c5"),
    "LEVE": DelayBand("Leve (11–30 min)", 11, 30, "#3f9f5b"),
    "MODERADO": DelayBand("Moderado (31–60 min)", 31, 60, "#f28b16"),
    "CRITICO": DelayBand("Crítico (> 60 min)", 61, None, "#d9282f"),
}


@dataclass(frozen=True, slots=True)
class DelayRecord:
    employee_name: str
    work_date: date
    weekday: str
    shift_code: str
    shift_name: str
    planned_time: str | None
    actual_time: str | None
    delay_minutes: int
    tolerance_minutes: int = TOLERANCE_MINUTES

    @property
    def band(self) -> str:
        for key, band in DELAY_BANDS.items():
            if self.delay_minutes >= band.minimum_minutes and (
                band.maximum_minutes is None or self.delay_minutes <= band.maximum_minutes
            ):
                return key
        return "CRITICO"

    @property
    def excess_minutes(self) -> int:
        return max(0, self.delay_minutes - self.tolerance_minutes)


@dataclass(frozen=True, slots=True)
class DelayReport:
    period_start: date
    period_end: date
    records: list[DelayRecord]
    source_filename: str
    generated_at: datetime | None = None


def validate_delay_report(report: DelayReport) -> dict[str, Any]:
    """Return a human-readable quality check for a parsed delay report."""
    records = report.records
    issues: list[str] = []
    dates = [record.work_date for record in records]
    if not records:
        issues.append("Nenhum registro válido foi encontrado.")
    if report.period_start > report.period_end:
        issues.append("O período inicial é posterior ao período final.")
    if dates and (min(dates) != report.period_start or max(dates) != report.period_end):
        issues.append("O período informado não corresponde às datas dos registros.")
    if any(record.delay_minutes < 0 for record in records):
        issues.append("Há registros com atraso negativo.")
    if any(not record.employee_name or not record.shift_code for record in records):
        issues.append("Há registros sem colaborador ou turno identificável.")

    bands = Counter(record.band for record in records)
    checks = [
        {"key": "registros", "label": "Registros válidos", "value": len(records), "status": "OK" if records else "ERRO"},
        {"key": "periodo", "label": "Período conferido", "value": f"{report.period_start:%d/%m/%Y} a {report.period_end:%d/%m/%Y}", "status": "OK" if dates and not any("período" in issue.casefold() for issue in issues) else "ERRO"},
        {"key": "atrasos", "label": "Atrasos não negativos", "value": "Sim" if not any(record.delay_minutes < 0 for record in records) else "Não", "status": "OK" if not any(record.delay_minutes < 0 for record in records) else "ERRO"},
        {"key": "identificacao", "label": "Colaborador e turno identificáveis", "value": "Sim" if not any(not record.employee_name or not record.shift_code for record in records) else "Não", "status": "OK" if not any(not record.employee_name or not record.shift_code for record in records) else "ERRO"},
        {"key": "privacidade", "label": "CPF exibido", "value": "Não", "status": "OK"},
    ]
    return {
        "valid": not issues,
        "issues": issues,
        "checks": checks,
        "records": len(records),
        "employees": len({record.employee_name for record in records}),
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "bands": {key: bands[key] for key in DELAY_BANDS},
    }


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _parse_minutes(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, time):
        return value.hour * 60 + value.minute
    if isinstance(value, datetime):
        return value.hour * 60 + value.minute
    if isinstance(value, (int, float)):
        return round(float(value) * 24 * 60)
    match = re.fullmatch(r"\s*(\d{1,3}):(\d{2})\s*", str(value))
    if not match:
        raise ValueError(f"tempo inválido: {value!r}")
    return int(match.group(1)) * 60 + int(match.group(2))


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", _text(value))
    if not match:
        raise ValueError(f"data inválida: {value!r}")
    return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))


def _shift_parts(value: Any) -> tuple[str, str]:
    text = _text(value)
    match = re.match(r"\s*(\d{4})\s*-\s*(.*)", text)
    if match:
        return match.group(1), match.group(2).strip()
    return text[:20], text


def parse_delay_rows(rows: Iterable[Mapping[str, Any]]) -> list[DelayRecord]:
    rows = list(rows)
    if not rows:
        raise ValueError("O relatório de atrasos não possui linhas.")
    missing = REQUIRED_HEADERS - set(rows[0].keys())
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"O relatório não possui as colunas obrigatórias: {names}")

    records: list[DelayRecord] = []
    for row in rows:
        name = _text(row.get("Nome"))
        if not name or name.casefold() in {"resumo", "total"}:
            continue
        work_date = _parse_date(row.get("Data"))
        shift_code, shift_name = _shift_parts(row.get("Turno"))
        delay = _parse_minutes(row.get("Tempo de atraso"))
        records.append(
            DelayRecord(
                employee_name=name,
                work_date=work_date,
                weekday=_text(row.get("Data")).split(",", 1)[0],
                shift_code=shift_code,
                shift_name=shift_name,
                planned_time=_text(row.get("Primeiro ponto previsto")) or None,
                actual_time=_text(row.get("Primeiro ponto realizado")) or None,
                delay_minutes=delay,
            )
        )
    if not records:
        raise ValueError("O relatório de atrasos não possui ocorrências válidas.")
    return records


def parse_delay_workbook(path: str | Path) -> DelayReport:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Instale as dependências com: pip install -r automation/requirements.txt") from exc

    source = Path(path)
    sheets = read_workbook_sheets(source)
    rows = [row[:8] for row in sheets[0]] if sheets else []
    header_index = next((index for index, row in enumerate(rows) if "Nome" in row and "Tempo de atraso" in row), None)
    if header_index is None:
        raise ValueError("O relatório não possui as colunas obrigatórias.")
    headers = [str(value).strip() if value is not None else "" for value in rows[header_index]]
    records = parse_delay_rows(dict(zip(headers, row)) for row in rows[header_index + 1:] if any(value is not None for value in row))
    return DelayReport(
        period_start=min(record.work_date for record in records),
        period_end=max(record.work_date for record in records),
        records=records,
        source_filename=source.name,
    )
