import assert from "node:assert/strict";
import test from "node:test";
import { assertImportPeriod } from "./absenceImport.ts";
import { automationRequestError } from "./automationRequest.ts";
import { isAllowedAbsenceUpload, isAllowedDelayUpload } from "./securityRules.ts";

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

test("validates the internal automation token and report date contract", () => {
  assert.equal(automationRequestError("secret", "secret", "2026-08-14"), null);
  assert.equal(automationRequestError("secret", "wrong", "2026-08-14"), "UNAUTHORIZED");
  assert.equal(automationRequestError("secret", "secret", "14-08-2026"), "INVALID_DATE");
});
