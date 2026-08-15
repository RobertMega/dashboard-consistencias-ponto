from datetime import date

from automation.parser.metrics import calculate_metrics
from automation.parser.models import RawRecord
from automation.parser.normalizer import normalize_records


def record(name: str, day: int, balance: str, *, critical: bool = False):
    return RawRecord(
        employee_name=name,
        work_date=date(2026, 8, day),
        weekday="Seg",
        markings={"entrada_1": None, "saida_1": None, "entrada_2": None, "saida_2": None, "entrada_3": None, "saida_3": None},
        planned_markings=["08:00", "12:00", "14:00", "18:00"] if critical else ["08:00", "12:00"],
        planned_hours="08:00" if critical else "04:00",
        total_hours="00:00",
        original_balance=balance,
    )


def test_metrics_count_final_negative_and_critical_employees_once():
    b_record = record("B", 1, "00:00")
    b_record.markings = {"entrada_1": "08:00", "saida_1": "12:00", "entrada_2": None, "saida_2": None, "entrada_3": None, "saida_3": None}
    records = normalize_records([record("A", 1, "-01:00", critical=True), record("A", 2, "00:30", critical=True), b_record])
    metrics = calculate_metrics(records)
    assert metrics["saldos_finais_negativos"] == 0
    assert metrics["colaboradores_criticos"] == 1
    assert metrics["saldo_finais"][0]["saldo_final"] == 30


def test_metrics_conformity_uses_planned_journey_denominator():
    ok_record = record("A", 1, "00:00", critical=False)
    ok_record.markings = {"entrada_1": "08:00", "saida_1": "12:00", "entrada_2": None, "saida_2": None, "entrada_3": None, "saida_3": None}
    records = normalize_records([
        ok_record,
        record("B", 1, "00:00", critical=True),
        RawRecord(
            employee_name="C",
            work_date=date(2026, 8, 1),
            weekday="Sáb",
            markings={"entrada_1": None, "saida_1": None, "entrada_2": None, "saida_2": None, "entrada_3": None, "saida_3": None},
            planned_markings=[], planned_hours="00:00", total_hours="00:00", observation="Folga", original_balance="00:00",
        ),
    ])
    metrics = calculate_metrics(records)
    assert metrics["dias_com_jornada"] == 2
    assert metrics["registros_ok"] == 1
    assert metrics["taxa_conformidade"] == 50.0


def test_zero_load_days_are_informative_and_positive_load_without_marks_is_justification():
    records = normalize_records([
        RawRecord(
            employee_name="A",
            work_date=date(2026, 8, 1),
            weekday="Sáb",
            markings={"entrada_1": None, "saida_1": None, "entrada_2": None, "saida_2": None, "entrada_3": None, "saida_3": None},
            planned_markings=[], planned_hours="00:00", total_hours="00:00",
        ),
        RawRecord(
            employee_name="A",
            work_date=date(2026, 8, 2),
            weekday="Dom",
            markings={"entrada_1": None, "saida_1": None, "entrada_2": None, "saida_2": None, "entrada_3": None, "saida_3": None},
            planned_markings=[], planned_hours="08:00", total_hours="00:00",
        ),
    ])
    metrics = calculate_metrics(records)
    assert metrics["feriados_sem_jornada"] == 1
    assert metrics["ponto_a_justificar"] == 1
    assert metrics["colaboradores_criticos"] == 1
    assert metrics["taxa_conformidade"] == 0.0
