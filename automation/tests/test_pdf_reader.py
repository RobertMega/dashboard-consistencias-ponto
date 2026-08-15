from datetime import date
from pathlib import Path

from automation.parser.normalizer import normalize_records
from automation.parser.pdf_reader import _nearest_column, _parse_date, _row_values, parse_pdf


def test_date_and_column_mapping():
    assert _parse_date("11/08/2026") == date(2026, 8, 11)
    assert _nearest_column(94) == 1
    assert _nearest_column(766) == 16


def test_row_values_preserves_missing_columns():
    values = _row_values(
        [
            type("Fragment", (), {"x": 5, "text": "Ter, 11/08/2026"})(),
            type("Fragment", (), {"x": 93, "text": "07:51"})(),
            type("Fragment", (), {"x": 137, "text": "13:13"})(),
            type("Fragment", (), {"x": 670, "text": "08:00"})(),
        ]
    )
    assert values["data"] == "Ter, 11/08/2026"
    assert values["entrada_1"] == "07:51"
    assert "saida_2" not in values
    assert values["planned_hours"] == "08:00"


def test_sample_pdf_extracts_expected_period_and_population():
    sample = Path(__file__).parents[2] / "samples" / "jornada-exemplo.pdf"
    raw_records = parse_pdf(sample)
    records = normalize_records(raw_records)
    assert len({record.employee_name for record in records}) == 414
    assert len(records) == 4335
    assert min(record.work_date.isoformat() for record in records) == "2026-08-01"
    assert max(record.work_date.isoformat() for record in records) == "2026-08-11"
    assert all(not record.parse_warnings for record in records)
    assert all(record.planned_markings == [] for record in records)
    assert all(record.expected_marking_count in {2, 4} for record in records if record.is_planned_journey)
