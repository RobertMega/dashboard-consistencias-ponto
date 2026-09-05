from __future__ import annotations

import argparse
import inspect
import json
import logging
import os
import shutil
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from automation.download.ponto_vr import (
    PontoConfig,
    PontoDownloadError,
    PontoReportDefinition,
    download_report_file,
    previous_report_date,
)

LOGGER = logging.getLogger("dashboard-ponto-scheduler")


@dataclass(frozen=True)
class ScheduledJob:
    key: str
    definition: PontoReportDefinition
    endpoint: str
    timeout_seconds: int


@dataclass(frozen=True)
class JobResult:
    key: str
    status: str
    duration_seconds: float
    message: str = ""


@dataclass(frozen=True)
class RunResult:
    status: str
    target_date: date
    message: str = ""
    jobs: tuple[JobResult, ...] = ()


@contextmanager
def run_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    def try_create():
        try:
            return os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return None

    def owner_is_alive():
        try:
            owner_pid = int(lock_path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            return False
        if owner_pid <= 0:
            return False
        try:
            os.kill(owner_pid, 0)
        except PermissionError:
            return True
        except ProcessLookupError:
            return False
        except OSError:
            return False
        return True

    descriptor = try_create()
    if descriptor is None and not owner_is_alive():
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        descriptor = try_create()
    if descriptor is None:
        yield False
        return
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        yield True
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def _cleanup_download(file_path: Path, work_dir: Path) -> None:
    try:
        file_path.unlink(missing_ok=True)
        parent = file_path.parent
        if parent.parent == work_dir and parent.name.startswith("ponto-vr-"):
            shutil.rmtree(parent, ignore_errors=True)
    except OSError:
        LOGGER.warning("temporary_cleanup_failed")


def submit_report(
    base_url: str,
    token: str,
    file_path: Path | None = None,
    target_date: date | None = None,
    endpoint: str = "/api/automation/report",
    timeout_seconds: int = 120,
    **legacy,
) -> dict:
    file_path = file_path or legacy.get("pdf_path")
    if file_path is None or target_date is None:
        raise ValueError("arquivo e data do relatório são obrigatórios")
    boundary = "----DashboardPonto" + uuid.uuid4().hex
    content = file_path.read_bytes()
    filename = file_path.name.encode("ascii", "ignore")
    content_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else "application/vnd.ms-excel"
    body = b"--" + boundary.encode() + b"\r\n"
    body += b'Content-Disposition: form-data; name="file"; filename="' + filename + b'"\r\n'
    body += f"Content-Type: {content_type}\r\n\r\n".encode() + content + b"\r\n"
    body += b"--" + boundary.encode() + b"--\r\n"
    request = urllib.request.Request(
        base_url.rstrip("/") + endpoint,
        data=body,
        method="POST",
        headers={
            "content-type": f"multipart/form-data; boundary={boundary}",
            "x-automation-token": token,
            "x-report-date": target_date.isoformat(),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)
            if response.status >= 400:
                raise RuntimeError("ingestion_http_error")
            return payload
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("não foi possível enviar o relatório para o dashboard") from exc


def _job_timeout_seconds() -> int:
    raw = os.environ.get("PONTO_JOB_TIMEOUT_SECONDS", "600").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise PontoDownloadError("CONFIGURATION", "PONTO_JOB_TIMEOUT_SECONDS deve ser um inteiro positivo.") from exc
    if value <= 0:
        raise PontoDownloadError("CONFIGURATION", "PONTO_JOB_TIMEOUT_SECONDS deve ser um inteiro positivo.")
    return value


def scheduled_jobs(config: PontoConfig) -> tuple[ScheduledJob, ...]:
    timeout = _job_timeout_seconds()
    return (
        ScheduledJob("inconsistency", config.report_definitions["inconsistency"], "/api/automation/report", timeout),
        ScheduledJob("absence", config.report_definitions["absence"], "/api/automation/absence", timeout),
        ScheduledJob("delay", config.report_definitions["delay"], "/api/automation/delay", timeout),
    )


def _call_fetcher(fetcher, config: PontoConfig, target_date: date, definition: PontoReportDefinition):
    try:
        parameters = inspect.signature(fetcher).parameters.values()
        accepts_definition = any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters) or len(parameters) >= 3
    except (TypeError, ValueError):
        accepts_definition = True
    return fetcher(config, target_date, definition) if accepts_definition else fetcher(config, target_date)


def _call_submitter(submitter, *, base_url, token, file_path, target_date, definition, endpoint, timeout_seconds):
    return submitter(
        base_url=base_url,
        token=token,
        file_path=file_path,
        pdf_path=file_path,
        target_date=target_date,
        definition=definition,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
    )


def run_once(
    target_date: date,
    config: PontoConfig,
    *,
    fetcher=download_report_file,
    submitter=submit_report,
    base_url: str | None = None,
    token: str | None = None,
    dry_run: bool = False,
) -> RunResult:
    if dry_run:
        return RunResult("DRY_RUN", target_date, "configuração e data validadas")
    if not base_url or not token:
        return RunResult("FAILED", target_date, "APP_BASE_URL e AUTOMATION_TOKEN são obrigatórios.")
    with run_lock(config.work_dir / "scheduled.lock") as acquired:
        if not acquired:
            return RunResult("LOCKED", target_date, "já existe uma execução em andamento")
        job_results: list[JobResult] = []
        for job in scheduled_jobs(config):
            started = time.monotonic()
            file_path: Path | None = None
            try:
                remaining = job.timeout_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError
                job_config = replace(config, timeout_ms=max(1, min(config.timeout_ms, int(remaining * 1000))))
                file_path = _call_fetcher(fetcher, job_config, target_date, job.definition)
                remaining = job.timeout_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError
                response = _call_submitter(
                    submitter,
                    base_url=base_url,
                    token=token,
                    file_path=file_path,
                    target_date=target_date,
                    definition=job.definition,
                    endpoint=job.endpoint,
                    timeout_seconds=max(1, int(remaining)),
                )
                job_results.append(JobResult(job.key, "SUCCESS", time.monotonic() - started, str(response.get("status", "SUCCESS"))))
            except TimeoutError:
                LOGGER.error("scheduled_job_timeout job=%s", job.key)
                job_results.append(JobResult(job.key, "TIMEOUT", time.monotonic() - started, "TIMEOUT"))
            except PontoDownloadError as exc:
                LOGGER.error("scheduled_job_failed job=%s code=%s", job.key, exc.code)
                job_results.append(JobResult(job.key, "FAILED", time.monotonic() - started, exc.code))
            except Exception:
                LOGGER.exception("scheduled_job_failed job=%s", job.key)
                job_results.append(JobResult(job.key, "FAILED", time.monotonic() - started, "SUBMIT_FAILED"))
            finally:
                if file_path:
                    _cleanup_download(file_path, config.work_dir)
        successes = sum(job.status == "SUCCESS" for job in job_results)
        failures = len(job_results) - successes
        status = "SUCCESS" if failures == 0 else "PARTIAL" if successes else "FAILED"
        return RunResult(status, target_date, f"{successes}/{len(job_results)} bases atualizadas", tuple(job_results))


def main() -> int:
    parser = argparse.ArgumentParser(description="Baixa e processa os três relatórios D-1 do Ponto VR.")
    parser.add_argument("--date", dest="target_date", help="Data do relatório em AAAA-MM-DD; por padrão, D-1 em São Paulo.")
    parser.add_argument("--dry-run", action="store_true", help="Valida configuração/data sem acessar o portal.")
    args = parser.parse_args()
    config = PontoConfig.from_env()
    target = date.fromisoformat(args.target_date) if args.target_date else previous_report_date()
    result = run_once(target, config, base_url=os.environ.get("APP_BASE_URL"), token=os.environ.get("AUTOMATION_TOKEN"), dry_run=args.dry_run)
    print(json.dumps({
        "status": result.status,
        "target_date": result.target_date.isoformat(),
        "message": result.message,
        "jobs": [
            {"key": job.key, "status": job.status, "duration_seconds": round(job.duration_seconds, 3), "message": job.message}
            for job in result.jobs
        ],
    }, ensure_ascii=False))
    return 0 if result.status in {"SUCCESS", "DRY_RUN", "LOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
