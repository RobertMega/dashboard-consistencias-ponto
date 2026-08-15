from datetime import date

from automation.parser.models import RawRecord
from automation.parser.normalizer import expected_markings_from_planned_hours, normalize_record, parse_hhmm


def raw(*, planned_count=4, marking_count=4, planned_minutes="08:00", total_hours="08:00", observation=None, original_balance="00:00"):
    marking_values = ["08:00", "12:00", "14:00", "18:00", "19:00", "20:00"]
    marking_fields = ("entrada_1", "saida_1", "entrada_2", "saida_2", "entrada_3", "saida_3")
    markings = {field: (marking_values[index] if index < marking_count else None) for index, field in enumerate(marking_fields)}
    planned_markings = [f"{8 + index:02d}:00" for index in range(planned_count)]
    return RawRecord(
        employee_name="Pessoa Teste",
        work_date=date(2026, 8, 11),
        weekday="Ter",
        markings=markings,
        planned_markings=planned_markings,
        total_hours=total_hours,
        planned_hours=planned_minutes,
        original_balance=original_balance,
        observation=observation,
    )


def test_parse_hhmm_uses_minutes_and_supports_negative():
    assert parse_hhmm("08:30") == 510
    assert parse_hhmm("-01:15") == -75
    assert parse_hhmm("00:00") == 0
    assert parse_hhmm("") is None


def test_expected_markings_are_configured_from_planned_hours():
    assert expected_markings_from_planned_hours("04:00") == 2
    assert expected_markings_from_planned_hours("08:00") == 4
    assert expected_markings_from_planned_hours("00:00") is None


def test_case_a_expected_four_realized_four_is_ok():
    record = normalize_record(raw(planned_count=4, marking_count=4))
    assert record.expected_marking_count == 4
    assert record.inconsistency_types == ["OK"]
    assert record.severity == "OK"


def test_case_b_expected_four_realized_zero_is_missing_marks():
    record = normalize_record(raw(planned_count=4, marking_count=0))
    assert record.inconsistency_types == ["PONTO_A_JUSTIFICAR"]
    assert record.severity == "CRITICA"


def test_case_c_expected_four_realized_three_is_odd_before_quantity_comparison():
    record = normalize_record(raw(planned_count=4, marking_count=3))
    assert record.inconsistency_types == ["MARCACAO_IMPAR"]
    assert record.severity == "CRITICA"


def test_case_d_expected_four_realized_two_is_incomplete():
    record = normalize_record(raw(planned_count=4, marking_count=2))
    assert record.inconsistency_types == ["MARCACOES_INCOMPLETAS"]
    assert record.severity == "ATENCAO"


def test_case_e_expected_four_realized_five_is_odd():
    record = normalize_record(raw(planned_count=4, marking_count=5))
    assert record.inconsistency_types == ["MARCACAO_IMPAR"]


def test_case_f_expected_four_realized_six_is_more_than_expected():
    record = normalize_record(raw(planned_count=4, marking_count=6))
    assert record.inconsistency_types == ["MAIS_QUE_PREVISTO"]
    assert record.severity == "ATENCAO"


def test_case_g_expected_two_realized_two_is_ok():
    record = normalize_record(raw(planned_count=2, marking_count=2, planned_minutes="04:00", total_hours="04:00"))
    assert record.expected_marking_count == 2
    assert record.inconsistency_types == ["OK"]


def test_four_hours_with_one_marking_is_odd():
    record = normalize_record(raw(planned_count=2, marking_count=1, planned_minutes="04:00", total_hours="00:00"))
    assert record.expected_marking_count == 2
    assert record.inconsistency_types == ["MARCACAO_IMPAR"]
    assert record.severity == "CRITICA"


def test_four_hours_with_zero_markings_is_missing_marks():
    record = normalize_record(raw(planned_count=2, marking_count=0, planned_minutes="04:00", total_hours="00:00"))
    assert record.expected_marking_count == 2
    assert record.inconsistency_types == ["PONTO_A_JUSTIFICAR"]
    assert record.severity == "CRITICA"


def test_case_h_folga_without_journey_is_informative_only():
    record = normalize_record(raw(planned_count=0, marking_count=0, planned_minutes="00:00", total_hours="00:00", observation="Folga"))
    assert record.inconsistency_types == ["SEM_JORNADA"]
    assert record.severity == "INFORMATIVO"
    assert record.status == "SEM_JORNADA"


def test_case_i_ferias_without_journey_is_informative_only():
    record = normalize_record(raw(planned_count=0, marking_count=0, planned_minutes="00:00", total_hours="00:00", observation="Férias"))
    assert record.inconsistency_types == ["SEM_JORNADA"]
    assert record.severity == "INFORMATIVO"
    assert record.status == "SEM_JORNADA"


def test_case_j_ferias_with_planned_journey_is_not_a_conflict_anymore():
    record = normalize_record(raw(planned_count=4, marking_count=0, observation="Férias"))
    assert record.inconsistency_types == ["PONTO_A_JUSTIFICAR"]
    assert record.severity == "CRITICA"


def test_case_k_extra_hours_do_not_create_more_than_expected():
    record = normalize_record(raw(planned_count=4, marking_count=4, total_hours="09:30"))
    assert record.inconsistency_types == ["OK"]


def test_invalid_planned_slots_are_ignored():
    invalid = raw(planned_count=0, marking_count=0, planned_minutes="00:00")
    invalid.planned_markings = ["", None, "00:00"]
    record = normalize_record(invalid)
    assert record.expected_marking_count is None


def test_zero_planned_hours_with_a_marking_is_point_without_journey():
    record = normalize_record(raw(planned_count=0, marking_count=1, planned_minutes="00:00"))
    assert record.inconsistency_types == ["PONTO_SEM_JORNADA"]
    assert record.severity == "ATENCAO"
