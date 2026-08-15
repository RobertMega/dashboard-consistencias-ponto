import { NextResponse } from "next/server";
import { requireAdmin } from "../../../../lib/auth";
import { prisma } from "../../../../lib/prisma";
import { mapDbRecord } from "../../../../lib/dashboardApi";
import { deriveFilteredView, filterRecords, filtersFromSearchParams } from "../../../../lib/dashboardFilters";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    await requireAdmin();
    const run = await prisma.reportRun.findFirst({ where: { isCurrent: true, status: "SUCCESS" }, orderBy: { processedAt: "desc" } });
    if (!run) return NextResponse.json({ error: "Nenhum relatório processado." }, { status: 404 });
    const records = (await prisma.dailyRecord.findMany({ where: { reportRunId: run.id }, orderBy: [{ date: "asc" }, { collaborator: "asc" }] })).map(mapDbRecord);
    const filters = filtersFromSearchParams(new URL(request.url).searchParams);
    const filtered = filterRecords(records, filters);
    const view = deriveFilteredView(filtered);
    const baseUrl = process.env.PARSER_FUNCTION_URL || (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : null);
    if (!baseUrl || !process.env.PARSER_SERVICE_TOKEN) return NextResponse.json({ error: "Exportação gerencial não está configurada neste ambiente." }, { status: 503 });
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/export`, { method: "POST", headers: { "content-type": "application/json", "x-parser-token": process.env.PARSER_SERVICE_TOKEN }, body: JSON.stringify({ summary: view.summary, rankings: view.rankings, records: filtered }) });
    if (!response.ok) return NextResponse.json({ error: "Não foi possível gerar a exportação." }, { status: 502 });
    const bytes = await response.arrayBuffer();
    return new NextResponse(bytes, { headers: { "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "content-disposition": `attachment; filename="dashboard_visao_filtrada_${run.periodEnd?.toISOString().slice(0, 10) || "periodo"}.xlsx"`, "cache-control": "private, no-store" } });
  } catch (error) {
    const message = error instanceof Error && error.message === "FORBIDDEN" ? "Acesso restrito a administradores." : "Não autenticado.";
    return NextResponse.json({ error: message }, { status: message === "Acesso restrito a administradores." ? 403 : 401 });
  }
}
