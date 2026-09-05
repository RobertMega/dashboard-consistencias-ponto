from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .workbook import read_workbook_sheets

from .workbook import read_workbook_sheets


REQUIRED_HEADERS = {"Nome", "Data"}
HEADER_ALIASES = {
    "nome": "Nome",
    "colaborador": "Nome",
    "nome colaborador": "Nome",
    "nome do colaborador": "Nome",
    "data": "Data",
    "dia": "Data",
    "data falta": "Data",
    "data da falta": "Data",
    "abono": "Abono",
    "abonado": "Abono",
    "abonado?": "Abono",
    "foi abonado": "Abono",
    "foi abonado?": "Abono",
    "motivo": "Motivo",
    "motivo falta": "Motivo",
    "motivo da falta": "Motivo",
    "justificativa": "Motivo",
    "observacao": "Motivo",
    "e folga?": "is_folga",
    "e folga": "is_folga",
    "gestor": "Gestor",
    "area": "Área",
    "setor": "Setor",
    "turno": "Turno",
}


@dataclass(frozen=True, slots=True)
class AbsenceRecord:
    collaborator: str
    work_date: date
    abono: str
    reason: str | None
    manager: str | None = None
    area: str | None = None
    sector: str | None = None
    shift: str | None = None
    is_day_off: str | None = None


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _fold(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFD", value.casefold()) if unicodedata.category(char) != "Mn")


def _header_key(value: Any) -> str:
    cleaned = _text(value).replace("\ufeff", "").replace("\u200b", "")
    return re.sub(r"\s+", " ", _fold(cleaned)).strip()


def _normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    source_headers: dict[str, str] = {}
    for raw_header, value in row.items():
        canonical = HEADER_ALIASES.get(_header_key(raw_header))
        if canonical is None:
            continue
        if canonical in normalized:
            first = source_headers[canonical]
            raise ValueError(f"O relatório possui colunas ambíguas para {canonical}: {first!r} e {_text(raw_header)!r}.")
        normalized[canonical] = value
        source_headers[canonical] = _text(raw_header)
    return normalized


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", _text(value))
    if not match:
        raise ValueError(f"data inválida: {value!r}")
    return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))


def _parse_abono(value: Any) -> str:
    normalized = _fold(_text(value))
    if not normalized:
        return ""
    if normalized in {"sim", "s", "true", "1", "yes", "y", "abonado", "abonada"}:
        return "Sim"
    if normalized in {"nao", "n", "false", "0", "no", "nao abonado", "nao abonada", "desabonado", "desabonada"}:
        return "Não"
    raise ValueError(f"Abono inválido: {value!r}")


def parse_absence_rows(rows: Iterable[Mapping[str, Any]]) -> list[AbsenceRecord]:
    rows = [_normalize_row(row) for row in rows]
    if not rows:
        raise ValueError("O relatório de faltas não possui linhas.")
    missing = REQUIRED_HEADERS - set(rows[0].keys())
    if missing:
        raise ValueError(f"O relatório não possui as colunas obrigatórias: {', '.join(sorted(missing))}")
    records: list[AbsenceRecord] = []
    for row in rows:
        name = _text(row.get("Nome"))
        if not name or _fold(name).startswith(("total", "resumo")):
            continue
        reason = _text(row.get("Motivo")) or None
        records.append(AbsenceRecord(name, _parse_date(row.get("Data")), _parse_abono(row.get("Abono")), reason, _text(row.get("Gestor")) or None, _text(row.get("Área")) or None, _text(row.get("Setor")) or None, _text(row.get("Turno")) or None, _text(row.get("is_folga")) or None))
    if not records:
        raise ValueError("O relatório de faltas não possui registros válidos.")
    return records


def _summary_abono_total(rows: list[tuple[Any, ...]]) -> int | None:
    for row in rows:
        if not row or _fold(_text(row[0])) != "total abonado":
            continue
        value = row[1] if len(row) > 1 else None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, float) and value.is_integer():
            return max(int(value), 0)
        match = re.fullmatch(r"\s*(\d+)\s*", _text(value))
        return int(match.group(1)) if match else None
    return None


def parse_absence_workbook(path: str | Path) -> tuple[list[AbsenceRecord], str, list[str], int | None]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Instale as dependências com: pip install -r automation/requirements.txt") from exc
    source = Path(path)
    for rows in read_workbook_sheets(source):
        header_index = next(
            (
                index
                for index, row in enumerate(rows)
                if REQUIRED_HEADERS.issubset(
                    {
                        canonical
                        for value in row
                        if value is not None
                        for canonical in [HEADER_ALIASES.get(_header_key(value))]
                        if canonical is not None
                    }
                )
            ),
            None,
        )
        if header_index is None:
            continue
        headers = [_text(value) for value in rows[header_index]]
        fields = sorted(_normalize_row(dict(zip(headers, headers))).keys())
        records = parse_absence_rows(dict(zip(headers, row)) for row in rows[header_index + 1:] if any(value is not None for value in row))
        return records, source.name, fields, _summary_abono_total(rows[header_index + 1:])
    raise ValueError("O relatório não possui as colunas obrigatórias.")


def validate_absence_rows(records: list[AbsenceRecord], fields: list[str] | None = None, summary_abono_total: int | None = None) -> dict[str, Any]:
    dates = [record.work_date for record in records]
    issues: list[str] = []
    if not records:
        issues.append("Nenhum registro válido foi encontrado.")
    if dates and min(dates) > max(dates):
        issues.append("O período inicial é posterior ao período final.")
    period_start = min(dates) if dates else None
    period_end = max(dates) if dates else None
    employees = len({record.collaborator for record in records})
    source_fields = set(fields or REQUIRED_HEADERS)
    abono_total = summary_abono_total if summary_abono_total is not None else sum(1 for record in records if record.abono == "Sim")
    field_labels = ["Colaborador", "Data"]
    if "Abono" in source_fields:
        field_labels.append("Abono")
    if "Motivo" in source_fields:
        field_labels.append("Motivo")
    if "is_folga" in source_fields:
        field_labels.append("É folga?")
    optional_fields = [
        ("Gestor", "manager"),
        ("Área", "area"),
        ("Setor", "sector"),
        ("Turno", "shift"),
    ]
    field_labels.extend(label for label, field in optional_fields if any(getattr(record, field) is not None for record in records))
    period_label = f"{period_start:%d/%m/%Y} a {period_end:%d/%m/%Y}" if period_start and period_end else "Não identificado"
    checks = [
        {"key": "registros", "label": "Registros válidos", "value": len(records), "status": "OK" if records else "ERRO"},
        {"key": "colaboradores", "label": "Colaboradores", "value": employees, "status": "OK" if employees else "ERRO"},
        {"key": "periodo", "label": "Período conferido", "value": period_label, "status": "OK" if dates and not any("período" in issue.casefold() for issue in issues) else "ERRO"},
        {"key": "campos", "label": "Campos disponíveis", "value": ", ".join(field_labels), "status": "OK"},
        {"key": "privacidade", "label": "CPF exibido", "value": "Não", "status": "OK"},
    ]
    if summary_abono_total is not None:
        checks.insert(3, {"key": "abono_total", "label": "Total abonado no resumo", "value": summary_abono_total, "status": "OK"})
    return {
        "valid": not issues,
        "issues": issues,
        "checks": checks,
        "records": len(records),
        "employees": employees,
        "period_start": period_start.isoformat() if period_start else None,
        "period_end": period_end.isoformat() if period_end else None,
        "statuses": dict(Counter(record.abono for record in records)),
        "abono_total": abono_total,
        "fields": field_labels,
        "source_profile": "enriquecida" if {"Abono", "Motivo"} <= source_fields else "simples",
    }
