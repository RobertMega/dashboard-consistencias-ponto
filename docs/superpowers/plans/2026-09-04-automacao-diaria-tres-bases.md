# Automação Diária das Três Bases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Baixar diariamente do Ponto VR os relatórios de inconsistência, falta e atraso referentes a D-1, processá-los em sequência e publicar cada base somente quando seu arquivo for válido.

**Architecture:** O downloader receberá três definições independentes de relatório e reutilizará a sessão autenticada do Ponto VR, escolhendo tipo, modelo e formato por definição. O worker executará os três jobs em fila, com timeout próprio, limpeza de temporários e resumo parcial; cada job enviará seu arquivo a um endpoint automático protegido por `AUTOMATION_TOKEN`. Os endpoints automáticos compartilharão o processamento e a persistência dos imports administrativos, enquanto as rotas e botões manuais continuarão usando autenticação e fluxo próprios.

**Tech Stack:** Python 3, Playwright, `openpyxl`/`xlrd`, pytest, Next.js App Router, TypeScript, Prisma/PostgreSQL e Windows Task Scheduler.

**Spec:** `docs/superpowers/specs/2026-09-04-automacao-diaria-tres-bases-design.md`

## Global Constraints

- A data automática será D-1 em `America/Sao_Paulo`.
- Os três relatórios serão processados em sequência, nunca em paralelo.
- Cada relatório terá configuração própria de tipo, modelo e extensão esperada.
- A falha de uma base não impedirá a tentativa das outras duas.
- Uma base anterior só será substituída depois de download, parsing, validação e persistência bem-sucedidos.
- Arquivos temporários, cookies e credenciais permanecerão fora do Git e serão removidos ao final de cada etapa.
- O botão manual continuará usando seus endpoints e seu fluxo atuais.
- Não exibir matrícula de colaboradores.

## File Map

- `automation/download/ponto_vr.py`: definições dos relatórios, leitura da configuração, sessão Playwright e download/validação dos artefatos.
- `automation/download/selectors.py`: seletores separados para exportação PDF e Excel.
- `automation/parser/workbook.py`: leitura comum de `.xlsx` e `.xls` para os parsers de falta e atraso.
- `automation/run_scheduled.py`: fila D-1, timeout individual, upload, lock e resumo dos três jobs.
- `automation/run_scheduled.ps1`: instalação de um único agendamento diário às 09:00.
- `web/lib/absenceImport.ts` e `web/lib/delayImport.ts`: processamento e persistência compartilhados pelos imports manual e automático.
- `web/app/api/automation/absence/route.ts` e `web/app/api/automation/delay/route.ts`: endpoints protegidos para os dois arquivos Excel.
- `web/lib/securityRules.ts`: aceitação controlada dos formatos Excel retornados pelo portal.
- `automation/.env.example`, `web/.env.example`, `README.md`, `docs/AUTOMACAO_LOCAL.md` e `docs/PRODUCAO_VERCEL.md`: configuração sem segredos e operação do agendador.

### Task 1: Modelar os três relatórios e tornar o downloader orientado por definição

**Files:**
- Modify: `automation/download/ponto_vr.py`
- Modify: `automation/download/selectors.py`
- Test: `automation/tests/test_ponto_vr.py`

**Interfaces:**
- Produces `PontoReportDefinition(key, report_type, report_model, expected_format)`.
- Produces `PontoConfig.report_definitions` with keys `inconsistency`, `absence` and `delay`.
- Keeps `download_report(config, report_date)` as a compatibility wrapper for the jornada em PDF.
- Adds `download_report_file(config, report_date, definition) -> Path`.

- [ ] **Step 1: Write the failing configuration and format tests**

```python
def test_config_contains_the_confirmed_ponto_vr_report_definitions():
    config = PontoConfig.from_env({"PONTO_CPF": "123", "PONTO_PASSWORD": "secret"})
    assert config.report_definitions["inconsistency"] == PontoReportDefinition(
        "inconsistency", "Jornada (espelho ponto)", "ROBERT - DASHBOARD", "pdf"
    )
    assert config.report_definitions["absence"] == PontoReportDefinition(
        "absence", "Faltas", "ROBERT - PAINEL GERENCIAL", "spreadsheet"
    )
    assert config.report_definitions["delay"] == PontoReportDefinition(
        "delay", "Atrasos", "ROBERT - DASHBOARD", "spreadsheet"
    )

def test_download_report_file_validates_the_expected_artifact_format(tmp_path):
    definition = PontoReportDefinition("absence", "Faltas", "ROBERT - PAINEL GERENCIAL", "spreadsheet")
    output = tmp_path / "faltas.xlsx"
    output.write_bytes(b"PK\x03\x04excel")
    assert validate_downloaded_file(output, definition) is True
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `pytest -q automation/tests/test_ponto_vr.py -k "confirmed_ponto_vr or expected_artifact"`

Expected: FAIL because the configuration has one model and the downloader has only a PDF path.

- [ ] **Step 3: Implement the report definitions and independent selector configuration**

Use these exact defaults:

```python
REPORT_DEFINITIONS = {
    "inconsistency": PontoReportDefinition("inconsistency", "Jornada (espelho ponto)", "ROBERT - DASHBOARD", "pdf"),
    "absence": PontoReportDefinition("absence", "Faltas", "ROBERT - PAINEL GERENCIAL", "spreadsheet"),
    "delay": PontoReportDefinition("delay", "Atrasos", "ROBERT - DASHBOARD", "spreadsheet"),
}
```

Read overrides from `PONTO_JOURNEY_REPORT_TYPE`, `PONTO_JOURNEY_REPORT_MODEL`, `PONTO_ABSENCE_REPORT_TYPE`, `PONTO_ABSENCE_REPORT_MODEL`, `PONTO_DELAY_REPORT_TYPE` and `PONTO_DELAY_REPORT_MODEL`; reject an empty override with `PontoDownloadError("CONFIGURATION", ...)`. Add `download_excel` selectors alongside `download_pdf`, with both selector sets configurable through environment variables. Select the configured report type and model exactly, select the PDF or Excel action according to `expected_format`, save a sanitized filename, and validate PDF magic bytes (`%PDF`) or spreadsheet signatures (`PK` for `.xlsx`, OLE header for `.xls`). Replace fixed eight-second waits with waits for the report form, generation response and visible download control; retain the existing Playwright timeout and `finally` browser cleanup.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run: `pytest -q automation/tests/test_ponto_vr.py`

Expected: PASS, including the pre-existing login, date, selector and compatibility tests.

- [ ] **Step 5: Commit the downloader unit**

```powershell
git add automation/download/ponto_vr.py automation/download/selectors.py automation/tests/test_ponto_vr.py
git commit -m "feat: configura tres relatorios do ponto vr"
```

### Task 2: Aceitar os arquivos Excel reais nos parsers de faltas e atrasos

**Files:**
- Create: `automation/parser/workbook.py`
- Modify: `automation/parser/absence_report.py`
- Modify: `automation/parser/delay_report.py`
- Modify: `automation/requirements.txt`
- Modify: `requirements.txt`
- Test: `automation/tests/test_workbook.py`
- Test: `automation/tests/test_absence_report.py`
- Test: `automation/tests/test_delay_report.py`

**Interfaces:**
- Produces `read_workbook_sheets(path) -> list[list[tuple[object, ...]]]`.
- Existing `parse_absence_workbook` and `parse_delay_workbook` consume the common reader and retain their current payload contracts.

- [ ] **Step 1: Write the failing reader and parser tests**

```python
def test_reader_dispatches_xlsx_and_xls_by_extension(tmp_path):
    xlsx = tmp_path / "relatorio.xlsx"
    xls = tmp_path / "relatorio.xls"
    make_xlsx_fixture(xlsx)
    make_xls_fixture(xls)
    assert read_workbook_sheets(xlsx)[0][0][0] == "Nome"
    assert read_workbook_sheets(xls)[0][0][0] == "Nome"

def test_absence_parser_accepts_the_xls_report(tmp_path):
    source = make_absence_xls_fixture(tmp_path / "faltas.xls")
    records, *_ = parse_absence_workbook(source)
    assert records[0].collaborator == "ANA"
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `pytest -q automation/tests/test_workbook.py automation/tests/test_absence_report.py automation/tests/test_delay_report.py -k "xls or dispatches"`

Expected: FAIL because the current parsers call `openpyxl.load_workbook` for every extension.

- [ ] **Step 3: Implement the workbook adapter**

Keep `openpyxl` for `.xlsx` and use `xlrd` for legacy `.xls`; normalize both readers to tuples, preserve empty cells, convert Excel date cells to `datetime`, and raise `ValueError("Formato Excel não suportado.")` for other extensions. Refactor both parsers to consume `read_workbook_sheets` without changing column detection, validation messages, CPF omission or metadata names. Add `xlrd>=2.0,<3` to both dependency files and keep test fixture generation isolated from production parsing.

- [ ] **Step 4: Run all parser tests and verify they pass**

Run: `pytest -q automation/tests/test_workbook.py automation/tests/test_absence_report.py automation/tests/test_delay_report.py automation/tests/test_absence_api.py`

Expected: PASS for `.xls`, `.xlsx`, validation and API payload tests.

- [ ] **Step 5: Commit the Excel compatibility unit**

```powershell
git add automation/parser/workbook.py automation/parser/absence_report.py automation/parser/delay_report.py automation/requirements.txt requirements.txt automation/tests/test_workbook.py automation/tests/test_absence_report.py automation/tests/test_delay_report.py
git commit -m "feat: suporta excel xls e xlsx nos parsers"
```

### Task 3: Extrair o processamento compartilhado de imports sem alterar o fluxo manual

**Files:**
- Create: `web/lib/absenceImport.ts`
- Create: `web/lib/delayImport.ts`
- Modify: `web/app/api/admin/absence-import/route.ts`
- Modify: `web/app/api/admin/delay-import/route.ts`
- Modify: `web/lib/securityRules.ts`
- Test: `web/lib/automatedImport.test.ts`
- Test: `web/lib/securityRules.test.ts`

**Interfaces:**
- Produces `processAndPersistAbsenceWorkbook(filename, bytes, expectedDate?)`.
- Produces `processAndPersistDelayWorkbook(filename, bytes, expectedDate?)`.
- Both helpers return the same summary fields currently returned by their manual routes and throw before changing `isCurrent` when validation or date checking fails.

- [ ] **Step 1: Write failing tests for shared import behavior and Excel extensions**

```typescript
test("accepts both legacy XLS and XLSX upload names", () => {
  assert.equal(isAllowedAbsenceUpload("faltas.xls", 100), true);
  assert.equal(isAllowedDelayUpload("atrasos.xls", 100), true);
  assert.equal(isAllowedAbsenceUpload("faltas.csv", 100), false);
});

test("rejects a workbook whose period is not the requested D-1 date", () => {
  assert.throws(
    () => assertImportPeriod("2026-08-14", { period_start: "2026-08-13", period_end: "2026-08-13" }),
    /REPORT_DATE_MISMATCH/,
  );
});
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `npm.cmd run test:filters -- --test-name-pattern="legacy XLS|period"`

Expected: FAIL because upload rules accept only `.xlsx` and no shared date assertion exists.

- [ ] **Step 3: Implement the shared helpers and preserve manual route behavior**

Move the existing parse, hash, duplicate/reactivation, transaction, current-run replacement and response-building code into the two helpers. The helpers must call `reportDateMatchesPeriod(expectedDate, payload.metadata)` when `expectedDate` is supplied, before opening the persistence transaction. Update `isAllowedAbsenceUpload` and `isAllowedDelayUpload` to accept `.xls` and `.xlsx`, while continuing to reject empty, oversized and non-Excel files. Make the existing admin routes call the helpers after `requireAdmin()` with no expected date so their user-facing workflow and status responses remain unchanged.

- [ ] **Step 4: Run the focused TypeScript tests and verify they pass**

Run: `npm.cmd run typecheck; npm.cmd run test:filters`

Expected: typecheck succeeds and the complete existing filter/security suite passes.

- [ ] **Step 5: Commit the shared import unit**

```powershell
git add web/lib/absenceImport.ts web/lib/delayImport.ts web/app/api/admin/absence-import/route.ts web/app/api/admin/delay-import/route.ts web/lib/securityRules.ts web/lib/automatedImport.test.ts web/lib/securityRules.test.ts
git commit -m "refactor: compartilha imports de faltas e atrasos"
```

### Task 4: Criar os endpoints automáticos de falta e atraso

**Files:**
- Create: `web/app/api/automation/absence/route.ts`
- Create: `web/app/api/automation/delay/route.ts`
- Test: `web/lib/automationRequest.test.ts`

**Interfaces:**
- `POST /api/automation/absence` accepts multipart field `file`, `x-automation-token` and `x-report-date`.
- `POST /api/automation/delay` accepts the same headers and field.
- Successful responses expose only status, source filename, period, record count, employees and validation/summary fields; internal errors and credentials are not returned.

- [ ] **Step 1: Write failing request-contract tests**

```typescript
test("automation request requires a valid token and an exact ISO date", () => {
  assert.equal(automationRequestError("secret", "wrong", "2026-08-14"), "UNAUTHORIZED");
  assert.equal(automationRequestError("secret", "secret", "14/08/2026"), "INVALID_DATE");
  assert.equal(automationRequestError("secret", "secret", "2026-08-14"), null);
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `npm.cmd run test:filters -- --test-name-pattern="automation request"`

Expected: FAIL because the request contract helper and both route contracts do not exist.

- [ ] **Step 3: Implement both protected endpoints**

Mirror the existing automation jornada endpoint for token comparison with `tokensMatch`, ISO date validation, multipart extraction and upload-size checks. Use the correct Excel filename and MIME handling, call the corresponding shared helper with `expectedDate`, map `REPORT_DATE_MISMATCH` to HTTP 422, missing token configuration to 503, invalid token to 401, malformed request to 400 and parser/persistence errors to a sanitized 422 response. Do not call `requireAdmin()` and do not create a browser session in these routes.

- [ ] **Step 4: Run typecheck and build**

Run: `npm.cmd run typecheck; npm.cmd run build`

Expected: both commands succeed and Next.js includes `/api/automation/absence` and `/api/automation/delay` as Node.js routes.

- [ ] **Step 5: Commit the automatic endpoints**

```powershell
git add web/app/api/automation/absence/route.ts web/app/api/automation/delay/route.ts web/lib/automationRequest.test.ts
git commit -m "feat: adiciona endpoints automaticos de faltas e atrasos"
```

### Task 5: Transformar o worker em fila sequencial com timeout por base

**Files:**
- Modify: `automation/run_scheduled.py`
- Modify: `automation/tests/test_scheduled_worker.py`

**Interfaces:**
- Produces `ScheduledJob(key, definition, endpoint, timeout_seconds)`.
- `run_once(...)` returns `RunResult` with an ordered per-job result list while retaining `SUCCESS`, `FAILED`, `DRY_RUN` and `LOCKED` compatibility statuses.
- `submit_report(base_url, token, file_path, target_date, endpoint, timeout_seconds)` sends the correct content type and date header.

- [ ] **Step 1: Write failing tests for order, continuation, cleanup and timeout**

```python
def test_worker_runs_inconsistency_absence_delay_in_order_and_continues_after_failure(tmp_path):
    events = []

    def fetcher(config, target_date, definition):
        events.append(("download", definition.key))
        if definition.key == "inconsistency":
            raise PontoDownloadError("DOWNLOAD_FAILED", "simulado")
        path = config.work_dir / f"{definition.key}.xlsx"
        path.write_bytes(b"PK\x03\x04")
        return path

    def submitter(**kwargs):
        events.append(("submit", kwargs["definition"].key))
        return {"status": "SUCCESS"}

    result = run_once(date(2026, 8, 14), config(tmp_path), fetcher=fetcher, submitter=submitter, base_url="http://localhost:3000", token="token")
    assert events == [("download", "inconsistency"), ("download", "absence"), ("submit", "absence"), ("download", "delay"), ("submit", "delay")]
    assert result.status == "PARTIAL"

def test_worker_assigns_a_timeout_to_each_job(tmp_path):
    result = run_once(date(2026, 8, 14), config(tmp_path), dry_run=True)
    assert [job.timeout_seconds for job in scheduled_jobs(config(tmp_path))] == [600, 600, 600]
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `pytest -q automation/tests/test_scheduled_worker.py -k "order_and_continues or timeout"`

Expected: FAIL because the worker currently knows only one PDF job and has no per-job result list.

- [ ] **Step 3: Implement the sequential job runner**

Create the ordered jobs `inconsistency -> absence -> delay`, map them to `/api/automation/report`, `/api/automation/absence` and `/api/automation/delay`, and read `PONTO_JOB_TIMEOUT_SECONDS` with default `600`. For every job, start a monotonic deadline, download with the job definition, upload with the remaining network timeout, record status/duration/error code, clean that file immediately, then continue. A failure or timeout marks only that job; all jobs are attempted. Return `SUCCESS` when all three succeed, `PARTIAL` when at least one succeeds and another fails, and `FAILED` when all fail. Preserve the lock around the complete queue, never log CPF/password/cookies or file contents, and return exit code 1 for `PARTIAL`/`FAILED` so Task Scheduler records the problem.

- [ ] **Step 4: Run the complete Python test suite**

Run: `pytest -q --ignore=_pytest_tmp --ignore=_pytest_tmp_stage1`

Expected: PASS, including the old single-PDF compatibility test and the new ordered queue tests.

- [ ] **Step 5: Commit the worker unit**

```powershell
git add automation/run_scheduled.py automation/tests/test_scheduled_worker.py
git commit -m "feat: processa tres bases em fila com timeout"
```

### Task 6: Agendar às 09:00 e documentar a configuração segura

**Files:**
- Modify: `automation/run_scheduled.ps1`
- Modify: `automation/.env.example`
- Modify: `web/.env.example`
- Modify: `README.md`
- Modify: `docs/AUTOMACAO_LOCAL.md`
- Modify: `docs/PRODUCAO_VERCEL.md`
- Test: `automation/tests/test_scheduled_worker.py`

**Interfaces:**
- The installer registers only `Dashboard-Consistencias-Ponto-0900` at `09:00`.
- The documented configuration contains report type/model variables, `PONTO_JOB_TIMEOUT_SECONDS`, `AUTOMATION_TOKEN`, `APP_BASE_URL`, credentials and parser settings without real values.

- [ ] **Step 1: Write the failing schedule and documentation assertions**

```python
def test_windows_schedule_registers_only_nine_without_old_times():
    content = (Path(__file__).parents[1] / "run_scheduled.ps1").read_text(encoding="utf-8")
    assert '@{ Name = "Dashboard-Consistencias-Ponto-0900"; Time = "09:00" }' in content
    assert 'Dashboard-Consistencias-Ponto-0800' not in content
    assert 'Dashboard-Consistencias-Ponto-1500' not in content
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `pytest -q automation/tests/test_scheduled_worker.py -k "nine_without_old_times"`

Expected: FAIL because the installer still registers 08:00 and 15:00.

- [ ] **Step 3: Implement the single daily schedule and safe examples**

Remove legacy tasks `0600`, `0800`, `1400` and `1500`, register only `0900`, set the Task Scheduler execution limit to 30 minutes, keep `MultipleInstances IgnoreNew`, and preserve the Windows credential prompt. Add the confirmed report variables and `PONTO_JOB_TIMEOUT_SECONDS="600"` to the local example files. Document the three report mappings, D-1 behavior, sequential execution, individual timeout, manual button availability and the first-run `--dry-run` command. Keep every credential value empty or clearly instructional and do not add `.env.local`, cookies, real PDFs or production spreadsheets.

- [ ] **Step 4: Run schedule, safety and repository checks**

Run:

```powershell
pytest -q automation/tests/test_scheduled_worker.py
git diff --check
rg -n "PONTO_PASSWORD=.+|PONTO_CPF=.+|AUTOMATION_TOKEN=.+|BEGIN PRIVATE|\.pdf$|\.xls[x]?$" --glob '!web/node_modules/**' --glob '!web/.next/**' --glob '!*.tsbuildinfo' .
```

Expected: schedule tests pass, `git diff --check` reports no errors, and the safety scan finds no real secrets or generated production files.

- [ ] **Step 5: Commit the scheduler and documentation unit**

```powershell
git add automation/run_scheduled.ps1 automation/.env.example web/.env.example README.md docs/AUTOMACAO_LOCAL.md docs/PRODUCAO_VERCEL.md automation/tests/test_scheduled_worker.py
git commit -m "feat: agenda atualizacao diaria as nove"
```

## Final Verification

- [ ] Run `pytest -q --ignore=_pytest_tmp --ignore=_pytest_tmp_stage1`.
- [ ] Run `npm.cmd run typecheck`.
- [ ] Run `npm.cmd run test:filters`.
- [ ] Run `npm.cmd run build`.
- [ ] Run `python -m py_compile automation/download/ponto_vr.py automation/run_scheduled.py automation/parser/workbook.py automation/parser/absence_report.py automation/parser/delay_report.py api/parse_absence.py api/parse_delay.py`.
- [ ] Run `git diff --check` and confirm that only files inside `dashboard-consistencias-ponto` changed.
- [ ] Execute `python -m automation.run_scheduled --dry-run` only after configuring local environment variables; confirm it validates configuration without opening the Ponto VR or uploading any file.
