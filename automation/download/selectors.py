from __future__ import annotations

from dataclasses import dataclass
from os import environ


@dataclass(frozen=True)
class PontoSelectors:
    cpf: tuple[str, ...] = (
        'input[placeholder*="Nome de usuário" i]',
        'input[name="cpf"]',
        'input[name="document"]',
        'input[placeholder*="CPF" i]',
    )
    password: tuple[str, ...] = ('input[name="password"]', 'input[type="password"][placeholder=""]', 'input[type="password"]')
    submit: tuple[str, ...] = ('button[type="submit"]', 'button:has-text("Entrar")', 'input[type="submit"]')
    date_from: tuple[str, ...] = ('input[name*="inicio" i]', 'input[name*="from" i]', 'input[placeholder*="início" i]')
    date_to: tuple[str, ...] = ('input[name*="fim" i]', 'input[name*="to" i]', 'input[placeholder*="fim" i]')
    date_range: tuple[str, ...] = ('input[bsdaterangepicker]', 'input[placeholder*="Selecionar" i]')
    report_type: tuple[str, ...] = ('ng-select.pm-select',)
    report_model: tuple[str, ...] = ('ng-select.pm-select',)
    generate: tuple[str, ...] = ('button.pm-primary', 'button:has-text("Gerar relatório")')
    download: tuple[str, ...] = ('button:has-text("Baixar")', 'button:has-text("Exportar")')
    download_pdf: tuple[str, ...] = ('a#relatorios-baixar-pdf', 'a:has-text("PDF")')
    download_excel: tuple[str, ...] = ('a#relatorios-baixar-excel', 'a:has-text("Excel")', 'a:has-text("XLS")')

    @classmethod
    def from_env(cls) -> "PontoSelectors":
        def values(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
            configured = environ.get(name, "").strip()
            return tuple(item.strip() for item in configured.split(",") if item.strip()) or default

        defaults = cls()
        return cls(
            cpf=values("PONTO_CPF_SELECTOR", defaults.cpf),
            password=values("PONTO_PASSWORD_SELECTOR", defaults.password),
            submit=values("PONTO_SUBMIT_SELECTOR", defaults.submit),
            date_from=values("PONTO_DATE_FROM_SELECTOR", defaults.date_from),
            date_to=values("PONTO_DATE_TO_SELECTOR", defaults.date_to),
            date_range=values("PONTO_DATE_RANGE_SELECTOR", defaults.date_range),
            report_type=values("PONTO_REPORT_TYPE_SELECTOR", defaults.report_type),
            report_model=values("PONTO_REPORT_MODEL_SELECTOR", defaults.report_model),
            generate=values("PONTO_GENERATE_SELECTOR", defaults.generate),
            download=values("PONTO_DOWNLOAD_SELECTOR", defaults.download),
            download_pdf=values("PONTO_DOWNLOAD_PDF_SELECTOR", defaults.download_pdf),
            download_excel=values("PONTO_DOWNLOAD_EXCEL_SELECTOR", defaults.download_excel),
        )
