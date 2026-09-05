from datetime import date
from pathlib import Path

from automation.download.ponto_vr import PontoConfig, PontoDownloadError
from automation.run_scheduled import run_lock, run_once, scheduled_jobs


def config(tmp_path: Path) -> PontoConfig:
    return PontoConfig(login_url="https://example.test/login", report_url="https://example.test/reports", cpf="123", password="secret", work_dir=tmp_path)


def test_worker_submits_each_downloaded_report_and_cleans_it(tmp_path):
    calls = []

    def fetcher(worker_config, target_date):
        output = worker_config.work_dir / "ponto-vr-test" / "report.pdf"
        output.parent.mkdir()
        output.write_bytes(b"%PDF-test")
        return output

    def submitter(**kwargs):
        calls.append(kwargs)
        return {"status": "SUCCESS"}

    result = run_once(date(2026, 8, 14), config(tmp_path), fetcher=fetcher, submitter=submitter, base_url="http://localhost:3000", token="token")
    assert result.status == "SUCCESS"
    assert len(calls) == 3
    assert [call["definition"].key for call in calls] == ["inconsistency", "absence", "delay"]
    assert all(call["pdf_path"].exists() is False for call in calls)


def test_worker_dry_run_does_not_download_or_submit(tmp_path):
    result = run_once(date(2026, 8, 14), config(tmp_path), dry_run=True)
    assert result.status == "DRY_RUN"


def test_worker_runs_inconsistency_absence_delay_in_order_and_continues_after_failure(tmp_path):
    events = []

    def fetcher(worker_config, target_date, definition):
        events.append(("download", definition.key))
        if definition.key == "inconsistency":
            raise PontoDownloadError("DOWNLOAD_FAILED", "simulado")
        suffix = ".pdf" if definition.expected_format == "pdf" else ".xlsx"
        path = worker_config.work_dir / f"{definition.key}{suffix}"
        path.write_bytes(b"%PDF-test" if suffix == ".pdf" else b"PK\x03\x04")
        return path

    def submitter(**kwargs):
        events.append(("submit", kwargs["definition"].key))
        return {"status": "SUCCESS"}

    result = run_once(
        date(2026, 8, 14),
        config(tmp_path),
        fetcher=fetcher,
        submitter=submitter,
        base_url="http://localhost:3000",
        token="token",
    )
    assert events == [
        ("download", "inconsistency"),
        ("download", "absence"),
        ("submit", "absence"),
        ("download", "delay"),
        ("submit", "delay"),
    ]
    assert result.status == "PARTIAL"


def test_worker_assigns_a_timeout_to_each_job(tmp_path):
    result = run_once(date(2026, 8, 14), config(tmp_path), dry_run=True)
    assert [job.timeout_seconds for job in scheduled_jobs(config(tmp_path))] == [600, 600, 600]


def test_windows_schedule_runs_at_eight_and_fifteen_without_legacy_tasks():
    script = Path(__file__).parents[1] / "run_scheduled.ps1"
    content = script.read_text(encoding="utf-8")

    assert 'Dashboard-Consistencias-Ponto-0800' in content
    assert 'Dashboard-Consistencias-Ponto-1500' in content
    assert '@{ Name = "Dashboard-Consistencias-Ponto-0800"; Time = "08:00" }' in content
    assert '@{ Name = "Dashboard-Consistencias-Ponto-1500"; Time = "15:00" }' in content
    assert 'Dashboard-Consistencias-Ponto-0600' in content
    assert 'Dashboard-Consistencias-Ponto-1400' in content
    assert 'Unregister-ScheduledTask' in content
    assert '-Password $taskPassword' in content
    assert 'Get-Credential' in content
    assert 'InteractiveToken' not in content


def test_stale_worker_lock_is_reclaimed(tmp_path):
    lock_path = tmp_path / "scheduled.lock"
    lock_path.write_text("999999999", encoding="ascii")

    with run_lock(lock_path) as acquired:
        assert acquired is True
        assert lock_path.exists()

    assert lock_path.exists() is False


def test_active_worker_lock_is_not_reclaimed(tmp_path):
    lock_path = tmp_path / "scheduled.lock"
    with run_lock(lock_path) as first_acquired:
        assert first_acquired is True
        with run_lock(lock_path) as second_acquired:
            assert second_acquired is False
