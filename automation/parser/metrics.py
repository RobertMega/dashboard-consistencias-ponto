from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .models import NormalizedRecord, minutes_to_hhmm


ISSUE_KEYS = (
    "PONTO_A_JUSTIFICAR",
    "MARCACAO_IMPAR",
    "MARCACOES_INCOMPLETAS",
    "MAIS_QUE_PREVISTO",
    "PONTO_SEM_JORNADA",
)


def _is_ok(record: NormalizedRecord) -> bool:
    return "OK" in record.inconsistency_types


def _is_actionable(record: NormalizedRecord) -> bool:
    return any(issue in ISSUE_KEYS for issue in record.inconsistency_types)


def _is_planned(record: NormalizedRecord) -> bool:
    return record.is_planned_journey


def employee_summaries(records: list[NormalizedRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[NormalizedRecord]] = defaultdict(list)
    for record in records:
        grouped[record.employee_name].append(record)

    summaries: list[dict[str, Any]] = []
    for employee_name, employee_records in sorted(grouped.items(), key=lambda item: item[0].casefold()):
        ordered = sorted(employee_records, key=lambda record: record.work_date)
        planned = [record for record in ordered if _is_planned(record)]
        valid_balance_records = [record for record in ordered if record.original_balance_minutes is not None]
        last = valid_balance_records[-1] if valid_balance_records else None
        inconsistencies = [record for record in ordered if _is_actionable(record)]
        critical = sum(record.severity == "CRITICA" for record in inconsistencies)
        attention = sum(record.severity == "ATENCAO" for record in inconsistencies)
        ok = sum(_is_ok(record) for record in planned)
        issue_count = len(inconsistencies)
        conformity = ok / len(planned) * 100 if planned else 0.0
        status = "CRITICO" if critical else "ATENCAO" if attention else "OK"
        summaries.append(
            {
                "employee_name": employee_name,
                "inconsistencias": issue_count,
                "criticas": critical,
                "atencao": attention,
                "registros_ok": ok,
                "dias_analisados": len(planned),
                "dias_com_jornada": len(planned),
                "conformidade": conformity,
                "status": status,
                "saldo_final": last.original_balance_minutes if last else None,
                "data_saldo_final": last.work_date.isoformat() if last else None,
                "tem_saldo_final": last is not None,
                "critico": critical > 0,
            }
        )
    return summaries


def _daily_inconsistencies(records: list[NormalizedRecord]) -> dict[str, dict[str, int]]:
    daily: dict[str, dict[str, int]] = {}
    for record in records:
        day = record.work_date.isoformat()
        row = daily.setdefault(day, {"total": 0, **{key.lower(): 0 for key in ISSUE_KEYS}})
        for issue in record.inconsistency_types:
            if issue in ISSUE_KEYS:
                row["total"] += 1
                row[issue.lower()] += 1
    return dict(sorted(daily.items()))


def calculate_metrics(records: list[NormalizedRecord]) -> dict[str, Any]:
    issue_counts = Counter(issue for record in records for issue in record.inconsistency_types)
    planned_records = [record for record in records if _is_planned(record)]
    records_ok = sum(_is_ok(record) for record in planned_records)
    days_with_journey = len(planned_records)
    summaries = employee_summaries(records)
    final_negative = sum(
        summary["saldo_final"] is not None and summary["saldo_final"] < 0
        for summary in summaries
    )
    critical_employees = sum(summary["critico"] for summary in summaries)
    unresolved_expected = sum(record.expected_marking_count is None for record in planned_records)
    zero_load_records = [record for record in records if not _is_planned(record) and record.marking_count == 0]
    planned_hours_distribution = Counter(minutes_to_hhmm(record.planned_minutes) for record in records)

    return {
        "colaboradores": len({record.employee_name for record in records}),
        "registros": len(records),
        "dias_com_jornada": days_with_journey,
        "dias_sem_jornada": len(records) - days_with_journey,
        # Compatibility alias; the canonical business label is
        # PONTO_A_JUSTIFICAR.
        "sem_marcacoes": issue_counts["PONTO_A_JUSTIFICAR"],
        "ponto_a_justificar": issue_counts["PONTO_A_JUSTIFICAR"],
        "marcacao_impar": issue_counts["MARCACAO_IMPAR"],
        "marcacoes_incompletas": issue_counts["MARCACOES_INCOMPLETAS"],
        "mais_que_previsto": issue_counts["MAIS_QUE_PREVISTO"],
        "ponto_sem_jornada": issue_counts["PONTO_SEM_JORNADA"],
        "conflito_jornada_evento": issue_counts["CONFLITO_JORNADA_EVENTO"],
        "registros_ok": records_ok,
        "colaboradores_criticos": critical_employees,
        "saldos_finais_negativos": final_negative,
        "taxa_conformidade": records_ok / days_with_journey * 100 if days_with_journey else 0.0,
        "registros_com_expectativa_indisponivel": unresolved_expected,
        "feriados_sem_jornada": len(zero_load_records),
        "saldo_finais": summaries,
        "issue_counts": dict(issue_counts),
        "inconsistencias_por_dia": _daily_inconsistencies(records),
        "distribuicao_horas_previstas": dict(sorted(planned_hours_distribution.items())),
    }


def rankings(records: list[NormalizedRecord], limit: int = 15, minimum_days: int = 5) -> dict[str, list[dict[str, Any]]]:
    summaries = employee_summaries(records)
    negative = sorted(
        summaries,
        key=lambda row: (
            -row["inconsistencias"],
            -row["criticas"],
            -row["atencao"],
            row["conformidade"],
            row["employee_name"].casefold(),
        ),
    )[:limit]
    positive_pool = [row for row in summaries if row["dias_analisados"] >= minimum_days]
    if not positive_pool:
        positive_pool = summaries
    positive = sorted(
        positive_pool,
        key=lambda row: (
            -row["conformidade"],
            -row["registros_ok"],
            -row["dias_analisados"],
            row["employee_name"].casefold(),
        ),
    )[:limit]
    return {
        "maiores_inconsistencias": [dict(row, posicao=index) for index, row in enumerate(negative, start=1)],
        "melhores_conformidades": [dict(row, posicao=index) for index, row in enumerate(positive, start=1)],
        "criterio_melhores_conformidades": f"mínimo de {minimum_days} dias com jornada; fallback para todos se não houver amostra suficiente",
    }
