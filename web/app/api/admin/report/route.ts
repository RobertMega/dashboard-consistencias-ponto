import { NextResponse } from "next/server";
import { ReportStatus } from "@prisma/client";
import { requireAdmin } from "../../../../lib/auth";
import { prisma } from "../../../../lib/prisma";
import { processUploadedPdf } from "../../../../lib/processUpload";
import { toDbRecord } from "../../../../lib/reportStore";
import { isAllowedUpload, MAX_UPLOAD_BYTES } from "../../../../lib/securityRules";

export const runtime = "nodejs";
const UPLOAD_LIMIT = Number(process.env.UPLOAD_MAX_BYTES || MAX_UPLOAD_BYTES);

export async function POST(request: Request) {
  let runId: string | null = null;
  try {
    await requireAdmin();
    const form = await request.formData();
    const entry = form.get("file");
    if (!(entry instanceof File)) return NextResponse.json({ error: "Selecione um arquivo PDF." }, { status: 400 });
    const filename = entry.name || "report.pdf";
    if (!isAllowedUpload(filename, entry.size, UPLOAD_LIMIT)) return NextResponse.json({ error: `O PDF deve ter entre 1 byte e ${Math.floor(UPLOAD_LIMIT / 1024 / 1024)} MB.` }, { status: 400 });
    const run = await prisma.reportRun.create({ data: { sourceFilename: filename.slice(0, 255), status: ReportStatus.PROCESSING } });
    runId = run.id;
    const { payload, excel } = await processUploadedPdf(filename, new Uint8Array(await entry.arrayBuffer()));
    const rows = payload.records.map((record) => toDbRecord(record as never, run.id));
    const start = new Date(`${payload.metadata.period_start}T00:00:00.000Z`);
    const end = new Date(`${payload.metadata.period_end}T00:00:00.000Z`);
    await prisma.$transaction(async (tx) => {
      await tx.dailyRecord.createMany({ data: rows });
      await tx.reportRun.updateMany({ where: { isCurrent: true }, data: { isCurrent: false } });
      await tx.reportRun.update({ where: { id: run.id }, data: { periodStart: start, periodEnd: end, processedAt: new Date(), status: ReportStatus.SUCCESS, totalRecords: rows.length, isCurrent: true, excelFilename: `dashboard_consistencias_ponto_${payload.metadata.period_end}.xlsx`, excelData: new Uint8Array(excel) } });
    });
    return NextResponse.json({ id: run.id, status: "SUCCESS", periodStart: payload.metadata.period_start, periodEnd: payload.metadata.period_end, totalRecords: rows.length });
  } catch (error) {
    const internalMessage = error instanceof Error ? error.message : "Falha desconhecida";
    if (runId) await prisma.reportRun.update({ where: { id: runId }, data: { status: ReportStatus.FAILED, errorMessage: internalMessage.slice(0, 2000) } }).catch(() => undefined);
    if (!(["UNAUTHENTICATED", "FORBIDDEN"].includes(internalMessage))) console.error("Report processing failed", { runId, message: internalMessage });
    const message = ["UNAUTHENTICATED", "FORBIDDEN"].includes(internalMessage) ? internalMessage : "Não foi possível processar o relatório. Consulte o histórico administrativo.";
    return NextResponse.json({ error: message === "FORBIDDEN" ? "Acesso restrito a administradores." : message === "UNAUTHENTICATED" ? "Não autenticado." : message }, { status: message === "UNAUTHENTICATED" ? 401 : message === "FORBIDDEN" ? 403 : 500 });
  }
}
