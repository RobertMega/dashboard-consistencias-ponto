import { createHash } from "node:crypto";
import { ReportStatus } from "@prisma/client";
import { delayRecordsForCreate } from "./delayStore.ts";
import { prisma } from "./prisma.ts";
import { assertImportPeriod } from "./absenceImport.ts";

type DelayProcessResponse = {
  payload?: {
    metadata: { period_start: string; period_end: string; source_filename: string; records: number; employees: number; tolerance_minutes: number; validation?: { checks: Array<{ label: string; value: string | number; status: string }> } };
    summary: { faixas: Record<string, number> };
    records: Array<Record<string, unknown>>;
  };
  excel?: string;
  pdf?: string;
  error?: string;
};

function parserUrl() {
  const base = process.env.PARSER_FUNCTION_URL || (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "");
  if (!base || !process.env.PARSER_SERVICE_TOKEN) throw new Error("Processador Python de atrasos não configurado.");
  return `${base.replace(/\/$/, "")}/api/parse-delay`;
}

async function processWorkbook(filename: string, bytes: Uint8Array) {
  const contentType = filename.toLowerCase().endsWith(".xls") ? "application/vnd.ms-excel" : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  const response = await fetch(parserUrl(), { method: "POST", headers: { "content-type": contentType, "content-length": String(bytes.byteLength), "x-file-name": filename, "x-parser-token": process.env.PARSER_SERVICE_TOKEN! }, body: Buffer.from(bytes) });
  const result = await response.json() as DelayProcessResponse;
  if (!response.ok || !result.payload || !result.excel) throw new Error(result.error || "Falha ao processar o Excel de atrasos.");
  return result;
}

export async function processAndPersistDelayWorkbook(filename: string, bytes: Uint8Array, expectedDate?: string) {
  const sourceHash = createHash("sha256").update(bytes).digest("hex");
  const sourceFilename = filename || "atrasos.xlsx";
  const existing = await prisma.delayReportRun.findUnique({ where: { sourceHash }, select: { id: true, status: true, sourceFilename: true, totalRecords: true, periodStart: true, periodEnd: true } });
  const refreshingExisting = existing?.status === ReportStatus.SUCCESS;
  const processed = await processWorkbook(sourceFilename, bytes);
  const payload = processed.payload!;
  assertImportPeriod(expectedDate, payload.metadata);
  const periodStart = new Date(`${payload.metadata.period_start}T00:00:00.000Z`);
  const periodEnd = new Date(`${payload.metadata.period_end}T00:00:00.000Z`);
  if (Number.isNaN(periodStart.getTime()) || Number.isNaN(periodEnd.getTime()) || !payload.records.length) throw new Error("O Excel de atrasos não produziu uma base válida.");
  const completed = await prisma.$transaction(async (tx) => {
    const run = existing
      ? await tx.delayReportRun.update({ where: { id: existing.id }, data: { status: ReportStatus.PROCESSING, sourceFilename } })
      : await tx.delayReportRun.create({ data: { sourceFilename, sourceHash, periodStart, periodEnd, status: ReportStatus.PROCESSING } });
    await tx.delayRecord.deleteMany({ where: { delayReportRunId: run.id } });
    await tx.delayRecord.createMany({ data: delayRecordsForCreate(run.id, payload.records as never) });
    await tx.delayReportRun.updateMany({ where: { isCurrent: true, id: { not: run.id } }, data: { isCurrent: false } });
    return tx.delayReportRun.update({ where: { id: run.id }, data: { periodStart, periodEnd, processedAt: new Date(), status: ReportStatus.SUCCESS, totalRecords: payload.records.length, toleranceMinutes: payload.metadata.tolerance_minutes, isCurrent: true, excelFilename: `relatorio_atrasos_${payload.metadata.period_end}.xlsx`, excelData: new Uint8Array(Buffer.from(processed.excel!, "base64")), pdfFilename: processed.pdf ? `relatorio_atrasos_${payload.metadata.period_end}.pdf` : null, pdfData: processed.pdf ? new Uint8Array(Buffer.from(processed.pdf, "base64")) : null } });
  });
  return { status: refreshingExisting ? "REFRESHED" : "SUCCESS", sourceFilename: payload.metadata.source_filename, periodStart: completed.periodStart.toISOString().slice(0, 10), periodEnd: completed.periodEnd.toISOString().slice(0, 10), totalRecords: completed.totalRecords, employees: payload.metadata.employees, bands: payload.summary.faixas, validation: payload.metadata.validation };
}
