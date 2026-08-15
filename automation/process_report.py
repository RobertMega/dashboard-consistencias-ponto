from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from automation.export.excel_exporter import export_excel
from automation.parser.metrics import calculate_metrics, rankings
from automation.parser.normalizer import normalize_records
from automation.parser.pdf_reader import parse_pdf


def _management_reading(metrics: dict) -> list[str]:
    reading: list[str] = []
    if metrics["ponto_a_justificar"]:
        reading.append(
            f"{metrics['ponto_a_justificar']} registros possuem jornada prevista, mas nenhuma marcação, e precisam de justificativa."
        )
    if metrics["marcacao_impar"]:
        reading.append(
            f"{metrics['marcacao_impar']} registros têm quantidade ímpar de marcações e exigem conferência do fechamento."
        )
    if metrics["colaboradores_criticos"]:
        reading.append(
            f"{metrics['colaboradores_criticos']} colaboradores possuem ao menos uma ocorrência crítica e devem orientar a tratativa gerencial."
        )
    reading.append(
        f"A taxa de conformidade calculada sobre {metrics['dias_com_jornada']} dias com jornada é {metrics['taxa_conformidade']:.2f}%."
    )
    if metrics["saldos_finais_negativos"]:
        reading.append(
            f"{metrics['saldos_finais_negativos']} colaboradores encerram o período com saldo final negativo."
        )
    return reading


def build_payload(records, pages: int | None = None, source_pdf: str | None = None):
    metrics = calculate_metrics(records)
    generated_at = datetime.now().isoformat(timespec="seconds")
    dates = [record.work_date for record in records]
    period_start = min(dates).isoformat() if dates else None
    period_end = max(dates).isoformat() if dates else None
    return {
        "metadata": {
            "generated_at": generated_at,
            "latest_update": generated_at,
            "source": "PDF Jornada",
            "source_pdf": source_pdf,
            "records": len(records),
            "employees": len({record.employee_name for record in records}),
            "pages": pages,
            "period_start": period_start,
            "period_end": period_end,
            "unparsed_records": 0,
            "errors": [],
        },
        "summary": metrics,
        "rankings": rankings(records),
        "readings": _management_reading(metrics),
        "records": [record.as_dict() for record in records],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Processa um relatório PDF de Jornada.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--excel", type=Path, help="Caminho do .xlsx de saída")
    parser.add_argument("--json", dest="json_path", type=Path, help="Caminho do JSON normalizado")
    args = parser.parse_args()

    raw_records = parse_pdf(args.pdf)
    records = normalize_records(raw_records)
    try:
        import fitz

        with fitz.open(str(args.pdf)) as document:
            pages = len(document)
    except ImportError:  # pragma: no cover - environment dependent
        pages = None
    payload = build_payload(records, pages=pages, source_pdf=str(args.pdf))
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.excel:
        export_excel(records, args.excel, str(args.pdf))

    terminal_summary = {
        key: payload["summary"][key]
        for key in (
            "colaboradores",
            "registros",
            "dias_com_jornada",
            "dias_sem_jornada",
            "feriados_sem_jornada",
            "ponto_a_justificar",
            "marcacao_impar",
            "marcacoes_incompletas",
            "mais_que_previsto",
            "ponto_sem_jornada",
            "registros_ok",
            "colaboradores_criticos",
            "saldos_finais_negativos",
            "taxa_conformidade",
            "registros_com_expectativa_indisponivel",
            "distribuicao_horas_previstas",
        )
    }
    print(json.dumps(payload["metadata"] | {"summary": terminal_summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
