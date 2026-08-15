import { Prisma, ReportStatus } from "@prisma/client";
import { prisma } from "./prisma";

type ApiRecord = {
  employee_name: string; work_date: string; weekday: string; markings: Record<string, string | null>;
  marking_count: number; expected_marking_count: number | null; total_minutes: number | null; planned_minutes: number | null;
  original_balance_minutes: number | null; calculated_daily_balance_minutes: number | null; observation: string | null;
  inconsistency_types: string[]; severity: string; status: string;
};

export function toDbRecord(record: ApiRecord, reportRunId: string): Prisma.DailyRecordUncheckedCreateInput {
  return {
    reportRunId, collaborator: record.employee_name, date: new Date(`${record.work_date}T00:00:00.000Z`),
    plannedHours: record.planned_minutes, expectedMarkings: record.expected_marking_count, markings: record.markings as Prisma.InputJsonValue,
    markingsCount: record.marking_count, totalHours: record.total_minutes, balance: record.original_balance_minutes,
    reason: record.observation, occurrenceType: record.inconsistency_types[0] ?? "OK", severity: record.severity,
    status: record.status, weekday: record.weekday, calculatedBalance: record.calculated_daily_balance_minutes,
    originalBalance: record.original_balance_minutes,
  };
}

export async function currentReport() {
  return prisma.reportRun.findFirst({ where: { isCurrent: true, status: ReportStatus.SUCCESS }, include: { dailyRecords: true }, orderBy: { processedAt: "desc" } });
}

export async function listReportRuns() {
  return prisma.reportRun.findMany({ select: { id: true, periodStart: true, periodEnd: true, sourceFilename: true, processedAt: true, status: true, totalRecords: true, errorMessage: true, createdAt: true, isCurrent: true }, orderBy: { createdAt: "desc" }, take: 50 });
}
