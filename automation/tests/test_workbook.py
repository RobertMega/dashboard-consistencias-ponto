from datetime import date

import pytest
from openpyxl import Workbook

from automation.parser.absence_report import parse_absence_workbook
from automation.parser.workbook import read_workbook_sheets


def _write_xlsx(path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Nome", "Data"])
    sheet.append(["ANA", date(2026, 8, 1)])
    workbook.save(path)


def _write_xls(path):
    xlwt = pytest.importorskip("xlwt")
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Faltas")
    for column, value in enumerate(["Nome", "Data", "Abono"]):
        sheet.write(0, column, value)
    for column, value in enumerate(["ANA", "01/08/2026", "Não"]):
        sheet.write(1, column, value)
    workbook.save(str(path))


def test_reader_supports_xlsx_and_xls(tmp_path):
    xlsx = tmp_path / "relatorio.xlsx"
    xls = tmp_path / "relatorio.xls"
    _write_xlsx(xlsx)
    _write_xls(xls)

    assert read_workbook_sheets(xlsx)[0][0][0] == "Nome"
    assert read_workbook_sheets(xls)[0][0][0] == "Nome"


def test_absence_parser_accepts_legacy_xls(tmp_path):
    source = tmp_path / "faltas.xls"
    _write_xls(source)

    records, *_ = parse_absence_workbook(source)

    assert records[0].collaborator == "ANA"
