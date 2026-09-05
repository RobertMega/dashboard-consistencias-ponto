import { createHash } from "node:crypto";
import { ReportStatus } from "@prisma/client";
import { absenceImportDecision } from "./absenceImportRules.ts";
import { absenceParserMode, normalizeParsedAbsencePayload, processAbsenceWorkbookLocally, resolveAbsenceParserUrl } from "./absenceParserService.ts";
import { deriveAbsenceView } from "./faltaMetrics.ts";
import type { AbsenceProcessPayload } from "./faltaReport.ts";
import { absenceRecordsForCreate } from "./faltaStore.ts";
import { prisma } from "./prisma.ts";
import { reportDateMatchesPeriod } from "./reportProcessingRules.ts";

type ProcessResponse = { payload?: AbsenceProcessPayload; error?: string };

export function assertImportPeriod(expectedDate: string | undefined, metadata: { period_start?: string | null; period_end?: string | null }) {
  if (expectedDate && !reportDateMatchesPeriod(expectedDate, metadata)) throw new Error("REPORT_DATE_MISMATCH");
}

async function processWorkbook(filename: string, bytes: Uint8Array) {
  if (absenceParserMode() === "local") return normalizeParsedAbsencePayload(await processAbsenceWorkbookLocally(filename, bytes));
  const token = process.env.PARSER_SERVICE_TOKEN;
  if (!token) throw new Error("Processador Python de faltas não configurado.");
  const contentType = filename.toLowerCase().endsWith(".xls") ? "application/vnd.ms-excel" : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  const response = await fetch(resolveAbsenceParserUrl("api/parse-absence"), { method: "POST", headers: { "content-type": contentType, "content-length": String(bytes.byteLength), "x-file-name": filename, "x-parser-token": token }, body: Buffer.from(bytes) });
  const result = await response.json() as ProcessResponse;
  if (!response.ok || !result.payload) throw new Error(result.error || "Falha ao processar o Excel de faltas.");
  return normalizeParsedAbsencePayload(result.payload);
}

export async function processAndPersistAbsenceWorkbook(filename: string, bytes: Uint8Array, expectedDate?: string) {
  const sourceHash = createHash("sha256").update(bytes).digest("hex");
  const existing = await prisma.absenceReportRun.findUnique({ where: { sourceHash }, select: { id: true, status: true, sourceFilename: true, totalRecords: true, abonoTotal: true, periodStart: true, periodEnd: true, isCurrent: true } });
  const decision = absenceImportDecision(existing);
  if (decision === "REACTIVATE") {
    assertImportPeriod(expectedDate, { period_start: existing!.periodStart.toISOString().slice(0, 10), period_end: existing!.periodEnd.toISOString().slice(0, 10) });
    const reactivated = await prisma.$transaction(async (tx) => {
      await tx.absenceReportRun.updateMany({ where: { isCurrent: true, id: { not: existing!.id } }, data: { isCurrent: false } });
      return tx.absenceReportRun.update({ where: { id: existing!.id }, data: { isCurrent: true, processedAt: new Date() } });
    });
    return { status: "REACTIVATED", sourceFilename: reactivated.sourceFilename, periodStart: reactivated.periodStart.toISOString().slice(0, 10), periodEnd: reactivated.periodEnd.toISOString().slice(0, 10), totalRecords: reactivated.totalRecords };
  }

  const sourceFilename = filename || "faltas.xlsx";
  const payload = await processWorkbook(sourceFilename, bytes);
  assertImportPeriod(expectedDate, payload.metadata);
  const periodStart = new Date(`${payload.metadata.period_start}T00:00:00.000Z`);
  const periodEnd = new Date(`${payload.metadata.period_end}T00:00:00.000Z`);
  if (Number.isNaN(periodStart.getTime()) || Number.isNaN(periodEnd.getTime()) || !payload.records.length) throw new Error("O Excel de faltas não produziu uma base válida.");
  const completed = await prisma.$transaction(async (tx) => {
    const run = existing
      ? await tx.absenceReportRun.update({ where: { id: existing.id }, data: { status: ReportStatus.PROCESSING, sourceFilename } })
      : await tx.absenceReportRun.create({ data: { sourceFilename, sourceHash, periodStart, periodEnd, status: ReportStatus.PROCESSING } });
    await tx.absenceRecord.deleteMany({ where: { absenceReportRunId: run.id } });
    await tx.absenceRecord.createMany({ data: absenceRecordsForCreate(run.id, payload.records) });
    await tx.absenceReportRun.updateMany({ where: { isCurrent: true, id: { not: run.id } }, data: { isCurrent: false } });
    return tx.absenceReportRun.update({ where: { id: run.id }, data: { periodStart, periodEnd, processedAt: new Date(), status: ReportStatus.SUCCESS, totalRecords: payload.records.length, abonoTotal: payload.metadata.abono_total ?? null, isCurrent: true } });
  });
  const view = deriveAbsenceView(payload.records);
  return { status: "SUCCESS", sourceFilename: payload.metadata.source_filename, periodStart: completed.periodStart.toISOString().slice(0, 10), periodEnd: completed.periodEnd.toISOString().slice(0, 10), totalRecords: completed.totalRecords, employees: view.summary.employees, summary: view.summary, validation: payload.metadata.validation };
}
