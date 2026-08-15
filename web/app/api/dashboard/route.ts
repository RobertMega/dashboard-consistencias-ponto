import { NextResponse } from "next/server";
import { Prisma } from "@prisma/client";
import { prisma } from "../../../lib/prisma";
import { requireSession } from "../../../lib/auth";
import { buildAlerts, buildReadings, mapDbRecord } from "../../../lib/dashboardApi";
import { deriveFilteredView, filterRecords, filtersFromSearchParams } from "../../../lib/dashboardFilters";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    const user = await requireSession();
    const url = new URL(request.url);
    const latestRun = await prisma.reportRun.findFirst({ orderBy: { createdAt: "desc" } });
    const run = await prisma.reportRun.findFirst({ where: { isCurrent: true, status: "SUCCESS" }, orderBy: { processedAt: "desc" } });
    if (!run) {
      const empty = deriveFilteredView([]);
      return NextResponse.json({
        metadata: { source: "PostgreSQL", records: 0, employees: 0, pages: null, period_start: null, period_end: null, unparsed_records: 0, errors: [], report_status: latestRun?.status },
        summary: empty.summary,
        baseSummary: empty.summary,
        rankings: empty.rankings,
        readings: buildReadings(empty.summary),
        alerts: buildAlerts(empty.summary),
        records: [],
        pagination: { page: 1, pageSize: 50, total: 0, totalPages: 1 },
        availableEmployees: [],
        user,
      }, { headers: { "cache-control": "private, no-store" } });
    }
    const filters = filtersFromSearchParams(url.searchParams);
    const simpleWhere: Prisma.DailyRecordWhereInput = { reportRunId: run.id };
    if (filters.type) simpleWhere.occurrenceType = filters.type;
    if (filters.employeeQuery) simpleWhere.collaborator = { contains: filters.employeeQuery, mode: "insensitive" };
    if (filters.severity) simpleWhere.severity = filters.severity;
    if (filters.status) simpleWhere.status = filters.status;
    const dateFrom = filters.dateFrom || filters.selectedDate;
    const dateTo = filters.dateTo || filters.selectedDate;
    if (dateFrom || dateTo) simpleWhere.date = { ...(dateFrom ? { gte: new Date(`${dateFrom}T00:00:00.000Z`) } : {}), ...(dateTo ? { lte: new Date(`${dateTo}T23:59:59.999Z`) } : {}) };
    const select = { collaborator: true, date: true, weekday: true, markings: true, markingsCount: true, expectedMarkings: true, totalHours: true, plannedHours: true, originalBalance: true, calculatedBalance: true, reason: true, occurrenceType: true, severity: true, status: true } as const;
    const [allDbRecords, filteredDbRecords, employeeRows] = await Promise.all([
      prisma.dailyRecord.findMany({ where: { reportRunId: run.id }, select, orderBy: [{ date: "asc" }, { collaborator: "asc" }] }),
      prisma.dailyRecord.findMany({ where: simpleWhere, select, orderBy: [{ date: "asc" }, { collaborator: "asc" }] }),
      prisma.dailyRecord.findMany({ where: { reportRunId: run.id }, select: { collaborator: true }, distinct: ["collaborator"], orderBy: { collaborator: "asc" } }),
    ]);
    const allRecords = allDbRecords.map(mapDbRecord);
    const filtered = filterRecords(filteredDbRecords.map(mapDbRecord), filters);
    const page = Math.max(Number(url.searchParams.get("page") || 1) || 1, 1);
    const pageSize = 50;
    const view = deriveFilteredView(filtered);
    const base = deriveFilteredView(allRecords);
    const comparison = await buildComparison(run, filters, view.summary);
    const names = employeeRows.map((row) => row.collaborator);
    const totalPages = Math.max(Math.ceil(filtered.length / pageSize), 1);
    const safePage = Math.min(page, totalPages);
    return NextResponse.json({
      metadata: { generated_at: run.processedAt?.toISOString(), latest_update: run.processedAt?.toISOString(), source: "PostgreSQL", source_pdf: run.sourceFilename, records: allRecords.length, employees: base.summary.colaboradores, pages: null, period_start: run.periodStart?.toISOString().slice(0, 10), period_end: run.periodEnd?.toISOString().slice(0, 10), unparsed_records: 0, errors: [], report_status: latestRun?.status },
      summary: view.summary,
      baseSummary: base.summary,
      rankings: view.rankings,
      readings: [...buildReadings(view.summary), ...(comparison.available ? [`A conformidade variou ${(comparison.taxa_conformidade?.delta ?? 0) >= 0 ? "positivamente" : "negativamente"} ${(Math.abs(comparison.taxa_conformidade?.delta ?? 0)).toFixed(1)} p.p. em relação ao período anterior.`] : [])].slice(0, 5),
      alerts: buildAlerts(view.summary),
      comparison,
      records: filtered.slice((safePage - 1) * pageSize, safePage * pageSize),
      pagination: { page: safePage, pageSize, total: filtered.length, totalPages },
      availableEmployees: names,
      user,
    }, { headers: { "cache-control": "private, no-store" } });
  } catch (error) {
    const status = error instanceof Error && error.message === "UNAUTHENTICATED" ? 401 : 500;
    return NextResponse.json({ error: status === 401 ? "Não autenticado." : "Não foi possível carregar o dashboard." }, { status });
  }
}

async function buildComparison(currentRun: { id: string; periodStart: Date | null; periodEnd: Date | null }, filters: ReturnType<typeof filtersFromSearchParams>, currentSummary: ReturnType<typeof deriveFilteredView>["summary"]) {
  if (!currentRun.periodStart || !currentRun.periodEnd) return { available: false };
  const currentDuration = Math.max(1, Math.round((currentRun.periodEnd.getTime() - currentRun.periodStart.getTime()) / 86400000) + 1);
  const candidates = await prisma.reportRun.findMany({ where: { id: { not: currentRun.id }, status: "SUCCESS", periodEnd: { lt: currentRun.periodStart } }, orderBy: { periodEnd: "desc" }, take: 10 });
  const previous = candidates.find((run) => run.periodStart && run.periodEnd && Math.abs((Math.round((run.periodEnd.getTime() - run.periodStart.getTime()) / 86400000) + 1) - currentDuration) <= Math.max(3, Math.round(currentDuration * 0.25)));
  if (!previous) return { available: false };
  const rows = (await prisma.dailyRecord.findMany({ where: { reportRunId: previous.id }, orderBy: [{ date: "asc" }, { collaborator: "asc" }] })).map(mapDbRecord);
  const previousFilters = { ...filters, dateFrom: "", dateTo: "", selectedDate: null };
  const previousView = deriveFilteredView(filterRecords(rows, previousFilters));
  const previousSummary = previousView.summary;
  const percentDelta = (current: number, previousValue: number) => previousValue ? (current - previousValue) / previousValue * 100 : 0;
  return {
    available: true,
    period_start: previous.periodStart?.toISOString().slice(0, 10),
    period_end: previous.periodEnd?.toISOString().slice(0, 10),
    taxa_conformidade: { current: currentSummary.taxa_conformidade, previous: previousSummary.taxa_conformidade, delta: currentSummary.taxa_conformidade - previousSummary.taxa_conformidade },
    ponto_a_justificar: { current: currentSummary.ponto_a_justificar, previous: previousSummary.ponto_a_justificar, deltaPercent: percentDelta(currentSummary.ponto_a_justificar, previousSummary.ponto_a_justificar) },
    marcacao_impar: { current: currentSummary.marcacao_impar, previous: previousSummary.marcacao_impar, deltaPercent: percentDelta(currentSummary.marcacao_impar, previousSummary.marcacao_impar) },
    colaboradores_criticos: { current: currentSummary.colaboradores_criticos, previous: previousSummary.colaboradores_criticos, delta: currentSummary.colaboradores_criticos - previousSummary.colaboradores_criticos },
  };
}
