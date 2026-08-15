from __future__ import annotations

import base64
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from automation.export.excel_exporter import export_excel
from automation.parser.normalizer import normalize_records
from automation.parser.pdf_reader import parse_pdf


MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def _process(pdf: bytes, filename: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="dashboard-ponto-") as directory:
        root = Path(directory)
        pdf_path = root / (Path(filename).name or "report.pdf")
        excel_path = root / "result.xlsx"
        pdf_path.write_bytes(pdf)
        records = normalize_records(parse_pdf(pdf_path))
        if not records:
            raise ValueError("Nenhum registro diário foi identificado.")
        export_excel(records, excel_path, filename)
        dates = [record.work_date for record in records]
        payload = {
            "metadata": {
                "source": "PDF Jornada",
                "source_pdf": filename,
                "records": len(records),
                "employees": len({record.employee_name for record in records}),
                "period_start": min(dates).isoformat(),
                "period_end": max(dates).isoformat(),
                "pages": None,
                "errors": [],
            },
            "records": [record.as_dict() for record in records],
        }
        return {"payload": payload, "excel": base64.b64encode(excel_path.read_bytes()).decode("ascii")}


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        expected = os.environ.get("PARSER_SERVICE_TOKEN")
        supplied = self.headers.get("x-parser-token")
        if not expected or not supplied or supplied != expected:
            _json(self, 401, {"error": "Não autorizado."})
            return
        content_length = int(self.headers.get("content-length", "0"))
        if content_length <= 0 or content_length > MAX_UPLOAD_BYTES:
            _json(self, 413, {"error": "PDF excede o limite permitido."})
            return
        try:
            body = self.rfile.read(content_length)
            result = _process(body, self.headers.get("x-file-name", "report.pdf"))
            _json(self, 200, result)
        except Exception:
            _json(self, 422, {"error": "Não foi possível processar o PDF."})

    def do_GET(self) -> None:  # noqa: N802
        _json(self, 405, {"error": "Método não permitido."})


__all__ = ["handler"]
