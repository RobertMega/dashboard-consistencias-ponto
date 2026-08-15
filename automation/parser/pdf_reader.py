from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .models import RawRecord


DATE_RE = re.compile(
    r"(?P<weekday>[A-Za-zÀ-ÿ]+),\s*(?P<date>\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
PERIOD_RE = re.compile(
    r"De\s+(\d{2}/\d{2}/\d{4})\s+at(?:é|e)\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
TIME_VALUE_RE = re.compile(r"^-?\d{1,3}:[0-5]\d$")

# Kept for compatibility with the parser unit tests and older callers. The
# production path below no longer uses these approximate PDF text positions.
CANONICAL_X = [5, 93, 137, 181, 225, 269, 313, 357, 401, 445, 489, 533, 579, 625, 670, 717, 765, 810]
COLUMN_NAMES = (
    "data",
    "entrada_1",
    "saida_1",
    "entrada_2",
    "saida_2",
    "entrada_3",
    "saida_3",
    "credit",
    "debit",
    "interval_hours",
    "normal_hours",
    "overtime_50",
    "overtime_100",
    "total_hours",
    "planned_hours",
    "additional_night",
    "original_balance",
    "observation",
)


@dataclass(slots=True, frozen=True)
class TextFragment:
    text: str
    x: float
    y: float


@dataclass(slots=True, frozen=True)
class CoordinateWord:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block: int
    line: int
    word: int


@dataclass(slots=True, frozen=True)
class CoordinateLayout:
    """Column centers for one visual report layout."""

    actual_centers: tuple[float, ...]
    field_centers: dict[str, float]
    source: str


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def _parse_date(value: str) -> date:
    day, month, year = (int(part) for part in value.split("/"))
    return date(year, month, day)


def _strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn")


def _fold(value: str) -> str:
    return _strip_accents(value).casefold()


def _extract_fragments(page: Any) -> list[TextFragment]:
    """Legacy pypdf adapter retained for compatibility with old callers."""
    fragments: list[TextFragment] = []

    def visitor(text: str, _cm: Any, tm: Any, _font: Any, _size: Any) -> None:
        text = _clean_text(text)
        if not text:
            return
        try:
            x, y = float(tm[4]), float(tm[5])
        except (IndexError, TypeError, ValueError):
            return
        fragments.append(TextFragment(text=text, x=x, y=y))

    page.extract_text(visitor_text=visitor)
    return fragments


def _group_lines(fragments: list[TextFragment], tolerance: float = 2.5) -> list[list[TextFragment]]:
    lines: list[list[TextFragment]] = []
    for fragment in sorted(fragments, key=lambda item: (item.y, item.x)):
        target = next((line for line in lines if abs(line[0].y - fragment.y) <= tolerance), None)
        if target is None:
            lines.append([fragment])
        else:
            target.append(fragment)
    for line in lines:
        line.sort(key=lambda item: item.x)
    return sorted(lines, key=lambda line: line[0].y)


def _line_text(line: list[TextFragment]) -> str:
    return _clean_text(" ".join(fragment.text for fragment in line))


def _nearest_column(x: float) -> int | None:
    distances = [(abs(x - start), index) for index, start in enumerate(CANONICAL_X)]
    distance, index = min(distances)
    return index if distance <= 22 else None


def _row_values(line: list[TextFragment]) -> dict[str, str]:
    values: dict[int, list[str]] = {}
    for fragment in line:
        column = _nearest_column(fragment.x)
        if column is None:
            continue
        values.setdefault(column, []).append(fragment.text)
    result: dict[str, str] = {}
    for index, pieces in values.items():
        result[COLUMN_NAMES[index]] = _clean_text(" ".join(pieces))
    return result


def _fitz_words(page: Any) -> list[CoordinateWord]:
    """Read words while preserving the PDF geometry supplied by PyMuPDF."""
    return [
        CoordinateWord(
            text=_clean_text(item[4]),
            x0=float(item[0]),
            y0=float(item[1]),
            x1=float(item[2]),
            y1=float(item[3]),
            block=int(item[5]),
            line=int(item[6]),
            word=int(item[7]),
        )
        for item in page.get_text("words", sort=False)
        if _clean_text(item[4])
    ]


def _group_coordinate_lines(words: list[CoordinateWord], tolerance: float = 2.5) -> list[list[CoordinateWord]]:
    lines: list[list[CoordinateWord]] = []
    for word in sorted(words, key=lambda item: (item.y0, item.x0)):
        target = next((line for line in lines if abs(line[0].y0 - word.y0) <= tolerance), None)
        if target is None:
            lines.append([word])
        else:
            target.append(word)
    for line in lines:
        line.sort(key=lambda item: item.x0)
    return sorted(lines, key=lambda line: line[0].y0)


def _line_coordinate_text(line: list[CoordinateWord]) -> str:
    return _clean_text(" ".join(word.text for word in line))


def _header_center(words: list[CoordinateWord], label: str) -> float | None:
    folded_label = _fold(label)
    for word in words:
        if _fold(word.text) == folded_label and 85 <= word.y0 <= 100:
            return word.x0
    return None


def _dedupe_centers(values: Iterable[float], minimum_distance: float = 3.0) -> tuple[float, ...]:
    result: list[float] = []
    for value in sorted(values):
        if not result or value - result[-1] >= minimum_distance:
            result.append(value)
    return tuple(result)


def _detect_layout(words: list[CoordinateWord]) -> CoordinateLayout:
    """Detect the six point columns and aggregate fields from the header."""
    header_words = [word for word in words if 78 <= word.y0 <= 101]
    actual_centers = _dedupe_centers(
        word.x0
        for word in header_words
        if 80 <= word.x0 < 240 and _fold(word.text) in {"entrada", "1ª", "2ª", "3ª"}
    )
    if len(actual_centers) < 6:
        actual_centers = (84.32, 110.72, 137.13, 163.54, 189.95, 216.35)
    else:
        actual_centers = actual_centers[:6]

    fallback_fields = {
        "credit": 242.76,
        "debit": 269.17,
        "interval_hours": 295.57,
        "normal_hours": 321.98,
        "overtime_50": 348.39,
        "overtime_100": 376.00,
        "total_hours": 403.60,
        "planned_hours": 430.61,
        "additional_night": 458.82,
        "original_balance": 487.63,
        "observation": 514.64,
    }
    labels = {
        "credit": "crédito",
        "debit": "débito",
        "interval_hours": "intervalo",
        "normal_hours": "normais",
        "overtime_50": "(50%)",
        "overtime_100": "(100%)",
        "total_hours": "totais",
        "planned_hours": "previstas",
        "additional_night": "noturno",
        "original_balance": "saldo",
        "observation": "motivo/observação",
    }
    field_centers = {
        key: _header_center(header_words, label) or fallback_fields[key]
        for key, label in labels.items()
    }
    return CoordinateLayout(
        actual_centers=actual_centers,
        field_centers=field_centers,
        source="header/points-and-aggregates",
    )


def _column_bounds(layout: CoordinateLayout) -> list[tuple[str, float, float | None]]:
    columns = [(f"point_{index}", center) for index, center in enumerate(layout.actual_centers)]
    columns.extend(layout.field_centers.items())
    columns.sort(key=lambda item: item[1])
    result: list[tuple[str, float, float | None]] = []
    for index, (name, center) in enumerate(columns):
        right = (center + columns[index + 1][1]) / 2 if index + 1 < len(columns) else None
        result.append((name, center, right))
    return result


def _coordinate_row_values(line: list[CoordinateWord], layout: CoordinateLayout) -> dict[str, Any]:
    columns = _column_bounds(layout)
    values: dict[str, str | None] = {}
    for index, (name, center, right) in enumerate(columns):
        left = (columns[index - 1][1] + center) / 2 if index else center - 14
        candidates = [
            word
            for word in line
            if word.x0 >= left and (right is None or word.x0 < right)
        ]
        if name.startswith("point_"):
            value = next((word.text for word in candidates if TIME_VALUE_RE.fullmatch(word.text)), None)
        else:
            value = _clean_text(" ".join(word.text for word in candidates)) or None
        values[name] = value

    actual = [values.get(f"point_{index}") for index in range(len(layout.actual_centers))]
    result: dict[str, Any] = {
        "entrada_1": actual[0] if len(actual) > 0 else None,
        "saida_1": actual[1] if len(actual) > 1 else None,
        "entrada_2": actual[2] if len(actual) > 2 else None,
        "saida_2": actual[3] if len(actual) > 3 else None,
        "entrada_3": actual[4] if len(actual) > 4 else None,
        "saida_3": actual[5] if len(actual) > 5 else None,
    }
    for field, center in layout.field_centers.items():
        result[field] = values.get(field)
    return result


def _find_name(lines: list[list[TextFragment]]) -> str | None:
    for line in lines:
        text = _line_text(line)
        if "Colaborador:" not in text:
            continue
        name = text.split("Colaborador:", 1)[1].strip(" :")
        if name:
            return name
    return None


def _find_coordinate_name(lines: list[list[CoordinateWord]]) -> str | None:
    for line in lines:
        text = _line_coordinate_text(line)
        marker = next((word for word in line if _fold(word.text).startswith("colaborador")), None)
        if marker is None:
            continue
        parts = [word.text for word in line if word.x0 > marker.x1]
        name = _clean_text(" ".join(parts))
        if name:
            return name
    return None


def _find_period(lines: list[list[TextFragment]]) -> tuple[date | None, date | None]:
    for line in lines:
        match = PERIOD_RE.search(_line_text(line))
        if match:
            return _parse_date(match.group(1)), _parse_date(match.group(2))
    return None, None


def _find_coordinate_period(lines: list[list[CoordinateWord]]) -> tuple[date | None, date | None]:
    for line in lines:
        match = PERIOD_RE.search(_line_coordinate_text(line))
        if match:
            return _parse_date(match.group(1)), _parse_date(match.group(2))
    return None, None


def _date_from_row(row: dict[str, str]) -> tuple[date, str] | None:
    match = DATE_RE.search(row.get("data", ""))
    if not match:
        return None
    return _parse_date(match.group("date")), match.group("weekday")


def _date_from_coordinate_line(line: list[CoordinateWord]) -> tuple[date, str] | None:
    date_word = next((word for word in line if re.fullmatch(r"\d{2}/\d{2}/\d{4}", word.text)), None)
    if date_word is None:
        return None
    weekday_word = next((word for word in line if word.x0 < date_word.x0 and word.x0 < 80), None)
    # Report metadata also contains dates (period and generation timestamp).
    # A daily row must have the weekday token in the leftmost Data cell.
    if weekday_word is None or not _fold(weekday_word.text).rstrip(",").startswith(("sab", "dom", "seg", "ter", "qua", "qui", "sex")):
        return None
    weekday = weekday_word.text.rstrip(",")
    return _parse_date(date_word.text), weekday


def _raw_from_row(
    row: dict[str, str],
    employee_name: str,
    page_number: int,
    line_number: int,
    report_start: date | None,
    report_end: date | None,
) -> RawRecord | None:
    parsed_date = _date_from_row(row)
    if parsed_date is None:
        return None
    work_date, weekday = parsed_date
    markings = {field: row.get(field) for field in ("entrada_1", "saida_1", "entrada_2", "saida_2", "entrada_3", "saida_3")}
    return RawRecord(
        employee_name=employee_name,
        work_date=work_date,
        weekday=weekday,
        markings=markings,
        planned_markings=[],
        credit=row.get("credit"),
        debit=row.get("debit"),
        interval_hours=row.get("interval_hours"),
        normal_hours=row.get("normal_hours"),
        overtime_50=row.get("overtime_50"),
        overtime_100=row.get("overtime_100"),
        total_hours=row.get("total_hours"),
        planned_hours=row.get("planned_hours"),
        additional_night=row.get("additional_night"),
        original_balance=row.get("original_balance"),
        observation=row.get("observation"),
        source_page=page_number,
        source_line=line_number,
        report_start=report_start,
        report_end=report_end,
    )


def _raw_from_coordinate_line(
    line: list[CoordinateWord],
    layout: CoordinateLayout,
    employee_name: str,
    page_number: int,
    line_number: int,
    report_start: date | None,
    report_end: date | None,
) -> RawRecord | None:
    parsed_date = _date_from_coordinate_line(line)
    if parsed_date is None:
        return None
    work_date, weekday = parsed_date
    row = _coordinate_row_values(line, layout)
    return RawRecord(
        employee_name=employee_name,
        work_date=work_date,
        weekday=weekday,
        markings={field: row.get(field) for field in ("entrada_1", "saida_1", "entrada_2", "saida_2", "entrada_3", "saida_3")},
        planned_markings=[],
        credit=row.get("credit"),
        debit=row.get("debit"),
        interval_hours=row.get("interval_hours"),
        normal_hours=row.get("normal_hours"),
        overtime_50=row.get("overtime_50"),
        overtime_100=row.get("overtime_100"),
        total_hours=row.get("total_hours"),
        planned_hours=row.get("planned_hours"),
        additional_night=row.get("additional_night"),
        original_balance=row.get("original_balance"),
        observation=row.get("observation"),
        source_page=page_number,
        source_line=line_number,
        report_start=report_start,
        report_end=report_end,
    )


def _parse_coordinate_page(page: Any, page_number: int) -> tuple[list[RawRecord], list[CoordinateWord], CoordinateLayout]:
    words = _fitz_words(page)
    lines = _group_coordinate_lines(words)
    employee_name = _find_coordinate_name(lines)
    if not employee_name:
        return [], words, _detect_layout(words)
    report_start, report_end = _find_coordinate_period(lines)
    layout = _detect_layout(words)
    records: list[RawRecord] = []
    for line_number, line in enumerate(lines, start=1):
        record = _raw_from_coordinate_line(
            line,
            layout,
            employee_name,
            page_number,
            line_number,
            report_start,
            report_end,
        )
        if record:
            records.append(record)
    return records, words, layout


def parse_pdf(path: str | Path, pages: Iterable[int] | None = None) -> list[RawRecord]:
    """Read daily rows using PyMuPDF word coordinates.

    ``pages`` is 1-based and exists for controlled prototype validation. When
    omitted, all pages are processed. Empty cells remain empty in their
    original coordinate slots; values are never shifted left.
    """
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Instale as dependências com: pip install -r automation/requirements.txt") from exc

    selected = set(pages) if pages is not None else None
    pdf_path = Path(path)
    records: list[RawRecord] = []
    with fitz.open(str(pdf_path)) as document:
        for page_number, page in enumerate(document, start=1):
            if selected is not None and page_number not in selected:
                continue
            page_records, _words, _layout = _parse_coordinate_page(page, page_number)
            records.extend(page_records)

    if not records:
        raise ValueError(f"Nenhum registro diário foi identificado em {pdf_path}")
    return records


def debug_coordinate_pages(path: str | Path, pages: Iterable[int]) -> None:
    """Print the coordinate prototype requested for selected 1-based pages."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Instale PyMuPDF para executar o protótipo posicional") from exc

    page_set = set(pages)
    with fitz.open(str(path)) as document:
        for page_number in sorted(page_set):
            records, words, layout = _parse_coordinate_page(document[page_number - 1], page_number)
            print(f"\n=== PÁGINA {page_number} | LAYOUT: {layout.source} ===")
            employee_name = records[0].employee_name if records else "não identificado"
            print(f"COLABORADOR: {employee_name}")
            print("CENTROS REALIZADOS:", list(layout.actual_centers))
            for record in records:
                planned = record.planned_markings if record.planned_markings else []
                actual = [record.markings.get(field) for field in ("entrada_1", "saida_1", "entrada_2", "saida_2", "entrada_3", "saida_3")]
                print(f"\nDATA: {record.work_date:%d/%m/%Y}")
                print("PLANEJADO: não disponível neste formato de PDF")
                print("REALIZADO:")
                print(actual)
                print(f"ESPERADAS: {sum(value is not None for value in planned)}")
                print(f"REALIZADAS: {sum(value is not None for value in actual)}")
                print("HORAS TOTAIS:", record.total_hours or "")
                print("HORAS PREVISTAS:", record.planned_hours or "")
                print("ADICIONAL NOTURNO:", record.additional_night or "")
                print("SALDO:", record.original_balance or "")
                print("MOTIVO:", record.observation or "")

            if page_number == 137:
                target = next((word for word in words if word.text == "03/08/2026"), None)
                if target:
                    row_words = [word for word in words if abs(word.y0 - target.y0) <= 2.5]
                    print("\nTOKENS BRUTOS DA LINHA 03/08/2026:")
                    for word in row_words:
                        print(f"{word.text} | {word.x0:.2f} | {word.x1:.2f} | {word.y0:.2f}")
