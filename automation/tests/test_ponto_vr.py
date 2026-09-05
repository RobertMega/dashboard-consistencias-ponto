from datetime import date, datetime
import sys
import types
from zoneinfo import ZoneInfo

import automation.download.ponto_vr as ponto_vr
import pytest
from automation.download.ponto_vr import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_TYPE,
    PontoConfig,
    PontoDownloadError,
    _fill_first,
    _wait_for_authenticated_redirect,
    download_report,
    login_succeeded,
    previous_report_date,
)
from automation.download.selectors import PontoSelectors


def test_config_reads_cpf_without_exposing_password():
    config = PontoConfig.from_env({
        "PONTO_LOGIN_URL": "https://example.test/login",
        "PONTO_CPF": "12345678900",
        "PONTO_PASSWORD": "secret",
    })
    assert config.cpf == "12345678900"
    assert config.password == "secret"
    assert "secret" not in repr(config)


def test_previous_report_date_is_calendar_d1_in_sao_paulo():
    current = datetime(2026, 8, 17, 7, tzinfo=ZoneInfo("America/Sao_Paulo"))
    assert previous_report_date(current) == date(2026, 8, 16)


def test_login_field_waits_for_spa_form_to_render():
    calls = []

    class Locator:
        def wait_for(self, **kwargs):
            calls.append(kwargs)

        def count(self):
            return 1

        def fill(self, value):
            calls.append({"fill": value})

    class Page:
        def locator(self, _selector):
            return type("LocatorChain", (), {"first": Locator()})()

    _fill_first(Page(), ("input[type='password']",), "secret", "senha", wait_ms=2000)

    assert calls[0] == {"state": "visible", "timeout": 2000}
    assert calls[1] == {"fill": "secret"}


def test_default_login_selector_matches_current_username_placeholder():
    assert "Nome de usuário" in PontoSelectors().cpf[0]


def test_login_is_not_successful_when_portal_returns_to_login_page():
    assert login_succeeded("https://app2.pontomais.com.br/login") is False
    assert login_succeeded("https://app2.pontomais.com.br/relatorios") is True


def test_login_waits_for_spa_redirect():
    calls = []

    class Page:
        def wait_for_url(self, predicate, timeout):
            calls.append(timeout)
            assert predicate("https://app2.pontomais.com.br/registrar-ponto") is True

    _wait_for_authenticated_redirect(Page(), 45000)
    assert calls == [45000]


def test_default_report_form_targets_current_pontomais_controls():
    selectors = PontoSelectors()

    assert selectors.date_range[0] == "input[bsdaterangepicker]"
    assert selectors.report_type[0] == "ng-select.pm-select"
    assert selectors.download_pdf[0] == "a#relatorios-baixar-pdf"
    assert DEFAULT_REPORT_TYPE == "Jornada (espelho ponto)"
    assert DEFAULT_REPORT_MODEL == "ROBERT - DASHBOARD"


def test_config_reads_report_model_and_form_selector_overrides():
    config = PontoConfig.from_env(
        {
            "PONTO_CPF": "12345678900",
            "PONTO_PASSWORD": "secret",
            "PONTO_REPORT_MODEL": "MODELO TESTE",
            "PONTO_DATE_RANGE_SELECTOR": "input[data-range]",
        }
    )

    assert config.report_model == "MODELO TESTE"
    assert config.selectors.date_range == ("input[data-range]",)


def test_config_contains_the_confirmed_ponto_vr_report_definitions():
    config = PontoConfig.from_env({"PONTO_CPF": "123", "PONTO_PASSWORD": "secret"})
    assert hasattr(ponto_vr, "PontoReportDefinition")
    definition = ponto_vr.PontoReportDefinition

    assert config.report_definitions["inconsistency"] == definition(
        "inconsistency", "Jornada (espelho ponto)", "ROBERT - DASHBOARD", "pdf"
    )
    assert config.report_definitions["absence"] == definition(
        "absence", "Faltas", "ROBERT - PAINEL GERENCIAL", "spreadsheet"
    )
    assert config.report_definitions["delay"] == definition(
        "delay", "Atrasos", "ROBERT - DASHBOARD", "spreadsheet"
    )


def test_download_report_file_validates_the_expected_artifact_format(tmp_path):
    assert hasattr(ponto_vr, "PontoReportDefinition")
    assert hasattr(ponto_vr, "validate_downloaded_file")
    definition = ponto_vr.PontoReportDefinition("absence", "Faltas", "ROBERT - PAINEL GERENCIAL", "spreadsheet")
    output = tmp_path / "faltas.xlsx"
    output.write_bytes(b"PK\x03\x04excel")

    assert ponto_vr.validate_downloaded_file(output, definition) is True


def test_config_overrides_each_ponto_vr_report_definition_independently():
    config = PontoConfig.from_env(
        {
            "PONTO_CPF": "123",
            "PONTO_PASSWORD": "secret",
            "PONTO_JOURNEY_REPORT_TYPE": "Jornada customizada",
            "PONTO_JOURNEY_REPORT_MODEL": "MODELO JORNADA",
            "PONTO_ABSENCE_REPORT_TYPE": "Faltas customizadas",
            "PONTO_ABSENCE_REPORT_MODEL": "MODELO FALTAS",
            "PONTO_DELAY_REPORT_TYPE": "Atrasos customizados",
            "PONTO_DELAY_REPORT_MODEL": "MODELO ATRASOS",
        }
    )

    assert config.report_definitions["inconsistency"].report_type == "Jornada customizada"
    assert config.report_definitions["inconsistency"].report_model == "MODELO JORNADA"
    assert config.report_definitions["absence"].report_type == "Faltas customizadas"
    assert config.report_definitions["absence"].report_model == "MODELO FALTAS"
    assert config.report_definitions["delay"].report_type == "Atrasos customizados"
    assert config.report_definitions["delay"].report_model == "MODELO ATRASOS"


@pytest.mark.parametrize(
    "name",
    (
        "PONTO_JOURNEY_REPORT_TYPE",
        "PONTO_JOURNEY_REPORT_MODEL",
        "PONTO_ABSENCE_REPORT_TYPE",
        "PONTO_ABSENCE_REPORT_MODEL",
        "PONTO_DELAY_REPORT_TYPE",
        "PONTO_DELAY_REPORT_MODEL",
    ),
)
def test_config_rejects_an_empty_report_override(name):
    with pytest.raises(PontoDownloadError) as error:
        PontoConfig.from_env({"PONTO_CPF": "123", "PONTO_PASSWORD": "secret", name: "  "})

    assert error.value.code == "CONFIGURATION"


def test_config_reads_independent_pdf_and_excel_download_selectors():
    config = PontoConfig.from_env(
        {
            "PONTO_CPF": "123",
            "PONTO_PASSWORD": "secret",
            "PONTO_DOWNLOAD_PDF_SELECTOR": "a[data-format='pdf']",
            "PONTO_DOWNLOAD_EXCEL_SELECTOR": "a[data-format='excel']",
        }
    )

    assert config.selectors.download_pdf == ("a[data-format='pdf']",)
    assert config.selectors.download_excel == ("a[data-format='excel']",)


def test_validate_downloaded_file_requires_the_matching_pdf_or_spreadsheet_signature(tmp_path):
    pdf = tmp_path / "jornada.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    xls = tmp_path / "faltas.xls"
    xls.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1workbook")
    html = tmp_path / "portal.html"
    html.write_bytes(b"<html>login</html>")

    pdf_definition = ponto_vr.PontoReportDefinition("inconsistency", "Jornada (espelho ponto)", "ROBERT - DASHBOARD", "pdf")
    spreadsheet_definition = ponto_vr.PontoReportDefinition("absence", "Faltas", "ROBERT - PAINEL GERENCIAL", "spreadsheet")

    assert ponto_vr.validate_downloaded_file(pdf, pdf_definition) is True
    assert ponto_vr.validate_downloaded_file(xls, spreadsheet_definition) is True
    assert ponto_vr.validate_downloaded_file(html, pdf_definition) is False
    assert ponto_vr.validate_downloaded_file(html, spreadsheet_definition) is False


def test_legacy_download_wrapper_uses_the_inconsistency_definition(monkeypatch, tmp_path):
    config = PontoConfig.from_env({"PONTO_CPF": "123", "PONTO_PASSWORD": "secret", "PONTO_WORK_DIR": str(tmp_path)})
    expected = tmp_path / "jornada.pdf"
    calls = []

    def fake_download(current_config, report_date, definition):
        calls.append((current_config, report_date, definition))
        return expected

    monkeypatch.setattr(ponto_vr, "download_report_file", fake_download, raising=False)
    monkeypatch.setitem(
        sys.modules,
        "playwright.sync_api",
        types.SimpleNamespace(
            TimeoutError=TimeoutError,
            sync_playwright=lambda: pytest.fail("the compatibility wrapper must not start Playwright"),
        ),
    )

    assert download_report(config, date(2026, 8, 14)) == expected
    assert calls == [(config, date(2026, 8, 14), config.report_definitions["inconsistency"])]


def test_download_report_file_closes_browser_when_page_creation_fails(monkeypatch, tmp_path):
    events = []

    class Context:
        def new_page(self):
            raise RuntimeError("page creation failed")

        def close(self):
            events.append("context.close")

    class Browser:
        def new_context(self, **_kwargs):
            return Context()

        def close(self):
            events.append("browser.close")

    class Chromium:
        def launch(self, **_kwargs):
            return Browser()

    class Playwright:
        chromium = Chromium()

    class PlaywrightManager:
        def __enter__(self):
            return Playwright()

        def __exit__(self, *_args):
            return None

    monkeypatch.setitem(
        sys.modules,
        "playwright.sync_api",
        types.SimpleNamespace(
            TimeoutError=TimeoutError,
            sync_playwright=lambda: PlaywrightManager(),
        ),
    )
    config = PontoConfig.from_env(
        {
            "PONTO_CPF": "123",
            "PONTO_PASSWORD": "secret",
            "PONTO_WORK_DIR": str(tmp_path),
        }
    )

    with pytest.raises(PontoDownloadError) as error:
        ponto_vr.download_report_file(
            config,
            date(2026, 8, 14),
            config.report_definitions["inconsistency"],
        )

    assert error.value.code == "DOWNLOAD_FAILED"
    assert events == ["context.close", "browser.close"]
