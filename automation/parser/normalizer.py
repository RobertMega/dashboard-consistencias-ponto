from __future__ import annotations

import re
import unicodedata

from .models import MARKING_FIELDS, NormalizedRecord, RawRecord


TIME_RE = re.compile(r"^(?P<sign>-)?(?P<hours>\d{1,6}):(?P<minutes>[0-5]\d)$")
EXPECTED_MARKINGS_SHORT_JOURNEY_MINUTES = 4 * 60
OBSERVATION_CODES = {
    "folga": "FOLGA",
    "ferias": "FERIAS",
    "afastamento inss": "AFASTAMENTO_INSS",
    "inss": "INSS",
    "licenca maternidade": "LICENCA_MATERNIDADE",
    "desligado": "DESLIGADO",
}
EVENT_KEYWORDS = (
    "folga",
    "feria",
    "afastamento",
    "licenca",
    "inss",
    "desligado",
    "abono",
)


def parse_hhmm(value: str | None) -> int | None:
    """Convert a report duration to minutes without using floating point."""
    if value is None:
        return None
    normalized = value.strip().replace(" ", "")
    if not normalized or normalized in {"-", "—", "–"}:
        return None
    match = TIME_RE.match(normalized)
    if not match:
        return None
    minutes = int(match["hours"]) * 60 + int(match["minutes"])
    return -minutes if match["sign"] else minutes


def expected_markings_from_planned_hours(planned_hours: str | None) -> int | None:
    """Return the configurable expected punch count for this PDF format.

    The report exposes only the aggregate ``Horas previstas`` value. Until an
    external schedule source exists, journeys up to four hours expect two
    punches and longer journeys expect four.
    """
    planned_minutes = parse_hhmm(planned_hours)
    if planned_minutes is None or planned_minutes <= 0:
        return None
    if planned_minutes <= EXPECTED_MARKINGS_SHORT_JOURNEY_MINUTES:
        return 2
    return 4


def _observation_code(observation: str | None) -> str | None:
    if not observation:
        return None
    normalized = _fold(observation.strip())
    if normalized in OBSERVATION_CODES:
        return OBSERVATION_CODES[normalized]
    if normalized.startswith("ajuste"):
        return "AJUSTE"
    return "OUTRA"


def _fold(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value.casefold()) if unicodedata.category(c) != "Mn")


def _is_event_observation(observation: str | None) -> bool:
    normalized = _fold(observation or "")
    return bool(normalized) and any(keyword in normalized for keyword in EVENT_KEYWORDS)


def _valid_planned_markings(values: list[str | None]) -> list[str]:
    return [value.strip() for value in values if value and value.strip() and value.strip() not in {"00:00", "-", "—", "–"}]


def _is_real_marking(value: str | None) -> bool:
    # The report uses blank cells for missing punches. A literal 00:00 in a
    # punch column is also treated as blank because calculated columns use it
    # as their zero value and midnight punches are not distinguishable here.
    return bool(value and value.strip() not in {"00:00", "-", "—", "–"})


def _incomplete_marking_slots(markings: dict[str, str | None]) -> bool:
    values = [_is_real_marking(markings.get(field)) for field in MARKING_FIELDS]
    # A later punch after an empty slot indicates a broken pair/sequence.
    seen_empty = False
    for present in values:
        if not present:
            seen_empty = True
        elif seen_empty:
            return True
    return False


def normalize_record(raw: RawRecord) -> NormalizedRecord:
    markings = {field: raw.markings.get(field) for field in MARKING_FIELDS}
    marking_count = sum(_is_real_marking(value) for value in markings.values())
    # This PDF has no individual planned-punch columns. Do not infer or copy
    # planned values from the realized-punch columns.
    planned_markings: list[str] = []
    planned = parse_hhmm(raw.planned_hours)
    expected_marking_count = expected_markings_from_planned_hours(raw.planned_hours)
    expected_marking_source = "planned_hours_threshold" if expected_marking_count is not None else "unavailable_in_pdf"
    total = parse_hhmm(raw.total_hours)
    original_balance = parse_hhmm(raw.original_balance)
    additional_night = parse_hhmm(raw.additional_night)
    daily_balance = total - planned if total is not None and planned is not None else None
    observation_code = _observation_code(raw.observation)
    warnings: list[str] = []
    if raw.total_hours and total is None:
        warnings.append("total_hours_invalid")
    if raw.planned_hours and planned is None:
        warnings.append("planned_hours_invalid")
    if raw.original_balance and original_balance is None:
        warnings.append("original_balance_invalid")

    issues: list[str] = []
    has_valid_journey = planned is not None and planned > 0
    if not has_valid_journey and marking_count == 0:
        # A zero-load day without punches is informational. It must not be
        # treated as a point inconsistency or penalize conformity.
        issues.append("SEM_JORNADA")
    elif has_valid_journey and marking_count == 0:
        # Do not infer "absence" or "falta". The operational treatment is
        # still pending justification by the manager.
        issues.append("PONTO_A_JUSTIFICAR")
    elif has_valid_journey and marking_count % 2:
        issues.append("MARCACAO_IMPAR")
    elif has_valid_journey and expected_marking_count is not None:
        if marking_count < expected_marking_count and marking_count > 0:
            issues.append("MARCACOES_INCOMPLETAS")
        elif marking_count > expected_marking_count:
            issues.append("MAIS_QUE_PREVISTO")
    elif not has_valid_journey and marking_count > 0:
        issues.append("PONTO_SEM_JORNADA")
    status = "COM_JORNADA"
    if not has_valid_journey:
        status = "SEM_JORNADA"

    if not issues:
        severity = "OK"
        issues = ["OK"]
    elif "SEM_JORNADA" in issues:
        severity = "INFORMATIVO"
    elif any(issue in issues for issue in ("PONTO_A_JUSTIFICAR", "MARCACAO_IMPAR")):
        severity = "CRITICA"
    else:
        severity = "ATENCAO"

    return NormalizedRecord(
        employee_name=raw.employee_name,
        work_date=raw.work_date,
        weekday=raw.weekday,
        markings=markings,
        planned_markings=planned_markings,
        marking_count=marking_count,
        expected_marking_count=expected_marking_count,
        expected_marking_source=expected_marking_source,
        credit_minutes=parse_hhmm(raw.credit),
        debit_minutes=parse_hhmm(raw.debit),
        interval_minutes=parse_hhmm(raw.interval_hours),
        normal_minutes=parse_hhmm(raw.normal_hours),
        overtime_50_minutes=parse_hhmm(raw.overtime_50),
        overtime_100_minutes=parse_hhmm(raw.overtime_100),
        total_minutes=total,
        planned_minutes=planned,
        additional_night_minutes=additional_night,
        original_balance_minutes=original_balance,
        calculated_daily_balance_minutes=daily_balance,
        observation=raw.observation,
        observation_code=observation_code,
        status=status,
        inconsistency_types=issues,
        severity=severity,
        is_planned_journey=has_valid_journey,
        parse_warnings=warnings,
        source_page=raw.source_page,
        source_line=raw.source_line,
    )


def normalize_records(records: list[RawRecord]) -> list[NormalizedRecord]:
    normalized = [normalize_record(record) for record in records]
    return sorted(normalized, key=lambda record: (record.work_date, record.employee_name.casefold()))
