import { NextResponse } from "next/server";
import { requireSession } from "../../../../lib/auth";
import { prisma } from "../../../../lib/prisma";
import { buildReadings, mapDbRecord } from "../../../../lib/dashboardApi";
import { deriveFilteredView } from "../../../../lib/dashboardFilters";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    await requireSession();
    const name = new URL(request.url).searchParams.get("name")?.trim();
    if (!name || name.length > 200) return NextResponse.json({ error: "Colaborador inválido." }, { status: 400 });
    const run = await prisma.reportRun.findFirst({ where: { isCurrent: true, status: "SUCCESS" }, orderBy: { processedAt: "desc" } });
    if (!run) return NextResponse.json({ error: "Nenhum relatório processado." }, { status: 404 });
    const records = (await prisma.dailyRecord.findMany({ where: { reportRunId: run.id, collaborator: name }, orderBy: { date: "asc" } })).map(mapDbRecord);
    const view = deriveFilteredView(records);
    return NextResponse.json({ name, records, summary: view.summary, readings: buildReadings(view.summary) }, { headers: { "cache-control": "private, no-store" } });
  } catch (error) { return NextResponse.json({ error: error instanceof Error && error.message === "UNAUTHENTICATED" ? "Não autenticado." : "Não foi possível carregar o detalhe." }, { status: error instanceof Error && error.message === "UNAUTHENTICATED" ? 401 : 500 }); }
}
