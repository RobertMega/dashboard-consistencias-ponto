from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo

from .selectors import PontoSelectors

DEFAULT_REPORT_URL = "https://app2.pontomais.com.br/relatorios"
DEFAULT_REPORT_TYPE = "Jornada (espelho ponto)"
DEFAULT_REPORT_MODEL = "ROBERT - DASHBOARD"
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


class PontoDownloadError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PontoReportDefinition:
    key: str
    report_type: str
    report_model: str
    expected_format: str


REPORT_DEFINITIONS = {
    "inconsistency": PontoReportDefinition("inconsistency", "Jornada (espelho ponto)", "ROBERT - DASHBOARD", "pdf"),
    "absence": PontoReportDefinition("absence", "Faltas", "ROBERT - PAINEL GERENCIAL", "spreadsheet"),
    "delay": PontoReportDefinition("delay", "Atrasos", "ROBERT - DASHBOARD", "spreadsheet"),
}


def login_succeeded(url: str) -> bool:
    return not url.rstrip("/").lower().endswith("/login")


def _wait_for_authenticated_redirect(page, timeout_ms: int) -> None:
    page.wait_for_url(lambda url: login_succeeded(url), timeout=timeout_ms)


@dataclass(frozen=True)
class PontoConfig:
    login_url: str
    report_url: str
    cpf: str
    password: str = field(repr=False)
    report_model: str = DEFAULT_REPORT_MODEL
    report_definitions: Mapping[str, PontoReportDefinition] = field(default_factory=lambda: dict(REPORT_DEFINITIONS))
    work_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()) / "dashboard-consistencias-ponto")
    timeout_ms: int = 45_000
    selectors: PontoSelectors = field(default_factory=PontoSelectors.from_env, repr=False)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "PontoConfig":
        values = dict(os.environ if env is None else env)
        login_url = values.get("PONTO_LOGIN_URL", "").strip() or DEFAULT_REPORT_URL
        report_url = values.get("PONTO_REPORT_URL", "").strip() or DEFAULT_REPORT_URL
        cpf = values.get("PONTO_CPF", "").strip()
        password = values.get("PONTO_PASSWORD", "")
        if not cpf or not password:
            raise PontoDownloadError("CONFIGURATION", "PONTO_CPF e PONTO_PASSWORD são obrigatórios.")
        legacy_report_model = values.get("PONTO_REPORT_MODEL", DEFAULT_REPORT_MODEL).strip() or DEFAULT_REPORT_MODEL
        return cls(
            login_url=login_url,
            report_url=report_url,
            cpf=cpf,
            password=password,
            report_model=legacy_report_model,
            report_definitions=_report_definitions_from_env(values, legacy_report_model),
            work_dir=Path(values.get("PONTO_WORK_DIR", "") or (Path(tempfile.gettempdir()) / "dashboard-consistencias-ponto")),
            timeout_ms=int(values.get("PONTO_TIMEOUT_MS", "45000")),
            selectors=_selectors_from_env(values),
        )


def _report_definitions_from_env(values: Mapping[str, str], legacy_report_model: str) -> dict[str, PontoReportDefinition]:
    configured = dict(REPORT_DEFINITIONS)
    overrides = {
        "inconsistency": ("PONTO_JOURNEY_REPORT_TYPE", "PONTO_JOURNEY_REPORT_MODEL"),
        "absence": ("PONTO_ABSENCE_REPORT_TYPE", "PONTO_ABSENCE_REPORT_MODEL"),
        "delay": ("PONTO_DELAY_REPORT_TYPE", "PONTO_DELAY_REPORT_MODEL"),
    }
    for key, (type_name, model_name) in overrides.items():
        definition = configured[key]
        report_type = _configured_value(values, type_name, definition.report_type)
        default_model = legacy_report_model if key == "inconsistency" and model_name not in values else definition.report_model
        report_model = _configured_value(values, model_name, default_model)
        configured[key] = PontoReportDefinition(key, report_type, report_model, definition.expected_format)
    return configured


def _configured_value(values: Mapping[str, str], name: str, default: str) -> str:
    if name not in values:
        return default
    value = values[name].strip()
    if not value:
        raise PontoDownloadError("CONFIGURATION", f"{name} não pode estar vazio.")
    return value


def _selectors_from_env(values: Mapping[str, str]) -> PontoSelectors:
    defaults = PontoSelectors()

    def configured(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(item.strip() for item in values.get(name, "").split(",") if item.strip()) or default

    return PontoSelectors(
        cpf=configured("PONTO_CPF_SELECTOR", defaults.cpf),
        password=configured("PONTO_PASSWORD_SELECTOR", defaults.password),
        submit=configured("PONTO_SUBMIT_SELECTOR", defaults.submit),
        date_from=configured("PONTO_DATE_FROM_SELECTOR", defaults.date_from),
        date_to=configured("PONTO_DATE_TO_SELECTOR", defaults.date_to),
        date_range=configured("PONTO_DATE_RANGE_SELECTOR", defaults.date_range),
        report_type=configured("PONTO_REPORT_TYPE_SELECTOR", defaults.report_type),
        report_model=configured("PONTO_REPORT_MODEL_SELECTOR", defaults.report_model),
        generate=configured("PONTO_GENERATE_SELECTOR", defaults.generate),
        download=configured("PONTO_DOWNLOAD_SELECTOR", defaults.download),
        download_pdf=configured("PONTO_DOWNLOAD_PDF_SELECTOR", defaults.download_pdf),
        download_excel=configured("PONTO_DOWNLOAD_EXCEL_SELECTOR", defaults.download_excel),
    )


def previous_report_date(now: datetime | None = None) -> date:
    current = now or datetime.now(SAO_PAULO)
    if current.tzinfo is None:
        current = current.replace(tzinfo=SAO_PAULO)
    return current.astimezone(SAO_PAULO).date() - timedelta(days=1)


def validate_downloaded_file(path: Path, definition: PontoReportDefinition) -> bool:
    try:
        signature = path.read_bytes()[:8]
    except OSError:
        return False
    if definition.expected_format == "pdf":
        return signature.startswith(b"%PDF")
    if definition.expected_format == "spreadsheet":
        return signature.startswith(b"PK") or signature.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    return False


def _fill_first(page, selectors: tuple[str, ...], value: str, label: str, wait_ms: int = 2_000, code: str = "LOGIN_FAILED") -> None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=wait_ms)
        except Exception:
            continue
        if locator.count() > 0:
            locator.fill(value)
            return
    raise PontoDownloadError(code, f"Campo de {label} não encontrado.")


def _click_first(page, selectors: tuple[str, ...], code: str, description: str, timeout_ms: int = 2_000) -> None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
        except Exception:
            continue
        if locator.count() > 0:
            locator.click()
            return
    raise PontoDownloadError(code, f"Controle de {description} não encontrado.")


def _wait_for_visible(page, selectors: tuple[str, ...], code: str, description: str, timeout_ms: int) -> None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
        except Exception:
            continue
        if locator.count() > 0:
            return
    raise PontoDownloadError(code, f"Controle de {description} não encontrado.")


def _normalized_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _select_option(page, selectors: tuple[str, ...], option: str, description: str, last: bool = False, timeout_ms: int = 8_000) -> None:
    for selector in selectors:
        controls = page.locator(selector)
        if controls.count() == 0:
            continue
        control = controls.last if last else controls.first
        try:
            control.wait_for(state="visible", timeout=timeout_ms)
            control.click()
        except Exception:
            continue
        options = page.locator(".ng-option:visible")
        for index in range(options.count()):
            candidate = options.nth(index)
            if _normalized_text(candidate.inner_text()) == option:
                candidate.click()
                return
    raise PontoDownloadError("REPORT_FORM_FAILED", f"Opção de {description} não encontrada.")


_MONTHS = {"janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


def _calendar_view_month(view) -> tuple[int, int] | None:
    headers = [_normalized_text(item) for item in view.locator("button.current").all_inner_texts()]
    if len(headers) < 2:
        return None
    month = _MONTHS.get(headers[0].casefold())
    try:
        year = int(headers[1])
    except ValueError:
        return None
    return (year, month) if month else None


def _set_report_date(page, selectors: tuple[str, ...], report_date: date, timeout_ms: int) -> None:
    date_input = None
    for selector in selectors:
        candidate = page.locator(selector).first
        try:
            candidate.wait_for(state="visible", timeout=2_000)
        except Exception:
            continue
        date_input = candidate
        break
    if date_input is None:
        raise PontoDownloadError("REPORT_FORM_FAILED", "Campo de período não encontrado.")
    date_input.click()
    dialog = page.locator('bs-daterangepicker-container[role="dialog"]:visible')
    try:
        dialog.wait_for(state="visible", timeout=timeout_ms)
    except Exception as exc:
        raise PontoDownloadError("REPORT_FORM_FAILED", "Calendário do período não abriu.") from exc
    target_month = (report_date.year, report_date.month)
    target_view = None
    for _ in range(24):
        views = dialog.locator("bs-days-calendar-view")
        for index in range(views.count()):
            view = views.nth(index)
            if _calendar_view_month(view) == target_month:
                target_view = view
                break
        if target_view is not None:
            break
        months = [_calendar_view_month(views.nth(index)) for index in range(views.count())]
        if not months or any(item is None for item in months):
            break
        if target_month > months[-1]:
            dialog.locator("button.next:visible").first.click()
        elif target_month < months[0]:
            dialog.locator("button.previous:visible").first.click()
        else:
            break
        page.wait_for_timeout(100)
    if target_view is None:
        raise PontoDownloadError("REPORT_FORM_FAILED", "Mês do período não encontrado no calendário.")
    days = target_view.locator('span[bsdatepickerdaydecorator]:not(.is-other-month)')
    target_day = next((days.nth(index) for index in range(days.count()) if _normalized_text(days.nth(index).inner_text()) == str(report_date.day)), None)
    if target_day is None:
        raise PontoDownloadError("REPORT_FORM_FAILED", "Dia do período não encontrado no calendário.")
    target_day.click()
    page.wait_for_timeout(100)
    start = dialog.locator("span.select-start.selected:visible")
    if start.count() > 0:
        start.first.click()
    expected = f"{report_date:%d/%m/%Y}-{report_date:%d/%m/%Y}"
    if _normalized_text(date_input.input_value()).replace(" ", "") != expected:
        raise PontoDownloadError("REPORT_FORM_FAILED", "O período selecionado não corresponde à data D-1.")


def _download_selectors(definition: PontoReportDefinition, selectors: PontoSelectors) -> tuple[str, ...]:
    if definition.expected_format == "pdf":
        return selectors.download_pdf
    if definition.expected_format == "spreadsheet":
        return selectors.download_excel
    raise PontoDownloadError("CONFIGURATION", f"Formato esperado inválido para {definition.key}.")


def _sanitized_filename(suggested_filename: str, definition: PontoReportDefinition, report_date: date) -> str:
    candidate = Path(suggested_filename).name
    allowed = {".pdf"} if definition.expected_format == "pdf" else {".xls", ".xlsx"}
    suffix = Path(candidate).suffix.lower()
    if suffix not in allowed:
        suffix = ".pdf" if definition.expected_format == "pdf" else ".xlsx"
    fallback = f"{definition.key}_{report_date.isoformat()}"
    stem = Path(candidate).stem or fallback
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or fallback
    return f"{safe_stem[:120]}{suffix}"


def _invalid_artifact_error(definition: PontoReportDefinition) -> PontoDownloadError:
    if definition.expected_format == "pdf":
        return PontoDownloadError("INVALID_PDF", "O arquivo baixado não é um PDF válido.")
    return PontoDownloadError("INVALID_SPREADSHEET", "O arquivo baixado não é uma planilha válida.")


def download_report_file(config: PontoConfig, report_date: date, definition: PontoReportDefinition) -> Path:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise PontoDownloadError("CONFIGURATION", "Instale Playwright e o Chromium antes de executar o download.") from exc
    config.work_dir.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="ponto-vr-", dir=config.work_dir))
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = None
            try:
                context = browser.new_context(accept_downloads=True)
                page = context.new_page()
                page.set_default_timeout(config.timeout_ms)
                page.goto(config.login_url, wait_until="domcontentloaded")
                _fill_first(page, config.selectors.cpf, config.cpf, "CPF")
                _fill_first(page, config.selectors.password, config.password, "senha")
                _click_first(page, config.selectors.submit, "LOGIN_FAILED", "login", config.timeout_ms)
                try:
                    _wait_for_authenticated_redirect(page, config.timeout_ms)
                except PlaywrightTimeoutError as exc:
                    raise PontoDownloadError("LOGIN_FAILED", "O portal não concluiu a autenticação do Ponto VR.") from exc
                page.goto(config.report_url, wait_until="domcontentloaded")
                _wait_for_visible(page, config.selectors.report_type, "REPORT_FORM_FAILED", "formulário do relatório", config.timeout_ms)
                _select_option(page, config.selectors.report_type, definition.report_type, "tipo do relatório", timeout_ms=config.timeout_ms)
                _select_option(page, config.selectors.report_model, definition.report_model, "modelo do relatório", last=True, timeout_ms=config.timeout_ms)
                _set_report_date(page, config.selectors.date_range, report_date, config.timeout_ms)
                try:
                    with page.expect_response(lambda response: response.request.method == "POST" and "/html_reports/" in response.url, timeout=config.timeout_ms):
                        _click_first(page, config.selectors.generate, "REPORT_FAILED", "geração do relatório", config.timeout_ms)
                except PlaywrightTimeoutError as exc:
                    raise PontoDownloadError("REPORT_FAILED", "O Ponto VR não concluiu a geração do relatório.") from exc
                _wait_for_visible(page, config.selectors.download, "REPORT_NOT_FOUND", "download do relatório", config.timeout_ms)
                _click_first(page, config.selectors.download, "REPORT_NOT_FOUND", "menu de download do relatório", config.timeout_ms)
                action_selectors = _download_selectors(definition, config.selectors)
                _wait_for_visible(page, action_selectors, "REPORT_NOT_FOUND", "formato de download", config.timeout_ms)
                with page.expect_download(timeout=config.timeout_ms) as download_info:
                    _click_first(page, action_selectors, "REPORT_NOT_FOUND", "download do relatório", config.timeout_ms)
                download = download_info.value
                output = run_dir / _sanitized_filename(download.suggested_filename, definition, report_date)
                download.save_as(str(output))
            except PlaywrightTimeoutError as exc:
                raise PontoDownloadError("DOWNLOAD_FAILED", "O Ponto VR não respondeu dentro do prazo.") from exc
            finally:
                if context is not None:
                    context.close()
                browser.close()
    except PontoDownloadError:
        raise
    except Exception as exc:
        raise PontoDownloadError("DOWNLOAD_FAILED", "Não foi possível baixar o relatório no Ponto VR.") from exc
    if not validate_downloaded_file(output, definition):
        raise _invalid_artifact_error(definition)
    return output


def download_report(config: PontoConfig, report_date: date) -> Path:
    return download_report_file(config, report_date, config.report_definitions["inconsistency"])
