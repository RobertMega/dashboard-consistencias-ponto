from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


MARKING_FIELDS = (
    "entrada_1",
    "saida_1",
    "entrada_2",
    "saida_2",
    "entrada_3",
    "saida_3",
)


@dataclass(slots=True)
class RawRecord:
    """One row as represented by the PDF, before business rules are applied."""

    employee_name: str
    work_date: date
    weekday: str
    markings: dict[str, str | None] = field(default_factory=dict)
    planned_markings: list[str | None] = field(default_factory=list)
    credit: str | None = None
    debit: str | None = None
    interval_hours: str | None = None
    normal_hours: str | None = None
    overtime_50: str | None = None
    overtime_100: str | None = None
    total_hours: str | None = None
    planned_hours: str | None = None
    additional_night: str | None = None
    original_balance: str | None = None
    observation: str | None = None
    source_page: int | None = None
    source_line: int | None = None
    report_start: date | None = None
    report_end: date | None = None


@dataclass(slots=True)
class NormalizedRecord:
    """Stable analytical contract consumed by Excel and the web dashboard."""

    employee_name: str
    work_date: date
    weekday: str
    markings: dict[str, str | None]
    planned_markings: list[str]
    marking_count: int
    expected_marking_count: int | None
    expected_marking_source: str
    credit_minutes: int | None
    debit_minutes: int | None
    interval_minutes: int | None
    normal_minutes: int | None
    overtime_50_minutes: int | None
    overtime_100_minutes: int | None
    total_minutes: int | None
    planned_minutes: int | None
    additional_night_minutes: int | None
    original_balance_minutes: int | None
    calculated_daily_balance_minutes: int | None
    observation: str | None
    observation_code: str | None
    status: str
    inconsistency_types: list[str]
    severity: str
    is_planned_journey: bool
    parse_warnings: list[str]
    source_page: int | None
    source_line: int | None

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["work_date"] = self.work_date.isoformat()
        return result


def minutes_to_hhmm(value: int | None) -> str:
    if value is None:
        return ""
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    return f"{sign}{absolute // 60:02d}:{absolute % 60:02d}"
