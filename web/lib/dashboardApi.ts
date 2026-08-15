import type { DailyRecord } from "@prisma/client";
import { deriveFilteredView } from "./dashboardFilters";
import type { DashboardRecord } from "./types";

type DashboardDbRecord = Pick<DailyRecord, "collaborator" | "date" | "weekday" | "markings" | "markingsCount" | "expectedMarkings" | "totalHours" | "plannedHours" | "originalBalance" | "calculatedBalance" | "reason" | "occurrenceType" | "severity" | "status">;

export function mapDbRecord(record: DashboardDbRecord): DashboardRecord {
  return {
    employee_name: record.collaborator,
    work_date: record.date.toISOString().slice(0, 10),
    weekday: record.weekday || "",
    markings: (record.markings || {}) as Record<string, string | null>,
    marking_count: record.markingsCount,
    expected_marking_count: record.expectedMarkings,
    total_minutes: record.totalHours,
    planned_minutes: record.plannedHours,
    original_balance_minutes: record.originalBalance,
    calculated_daily_balance_minutes: record.calculatedBalance,
    observation: record.reason,
    inconsistency_types: [record.occurrenceType],
    severity: record.severity as DashboardRecord["severity"],
    status: record.status,
    is_planned_journey: (record.plannedHours ?? 0) > 0,
  };
}

export function buildReadings(summary: ReturnType<typeof deriveFilteredView>["summary"]) {
  const readings: string[] = [`Neste contexto foram analisados ${summary.colaboradores} colaboradores em ${summary.dias_com_jornada} dias com jornada.`, `A taxa de conformidade foi de ${summary.taxa_conformidade.toFixed(1)}%.`];
  if (summary.colaboradores_criticos) readings.push(`${summary.colaboradores_criticos} colaboradores apresentaram ocorrÃªncia crÃ­tica.`);
  const principal = Object.entries(summary.issue_counts).filter(([type]) => type !== "OK" && type !== "SEM_JORNADA").sort(([, a], [, b]) => b - a)[0];
  if (principal) readings.push(`O principal desvio foi ${principal[0].replaceAll("_", " ").toLocaleLowerCase("pt-BR")}, com ${principal[1]} ocorrÃªncia(s).`);
  if (summary.colaboradores_reincidentes) readings.push(`${summary.colaboradores_reincidentes} colaboradores apresentaram reincidÃªncia.`);
  return readings.slice(0, 5);
}

export function buildAlerts(summary: ReturnType<typeof deriveFilteredView>["summary"]) {
  const alerts: string[] = [];
  if (summary.colaboradores_reincidentes) alerts.push(`${summary.colaboradores_reincidentes} colaborador(es) reincidente(s) requerem acompanhamento.`);
  if (summary.taxa_conformidade < 80 && summary.dias_com_jornada > 0) alerts.push(`A conformidade do contexto estÃ¡ abaixo de 80% (${summary.taxa_conformidade.toFixed(1)}%).`);
  if (summary.saldos_finais_negativos) alerts.push(`${summary.saldos_finais_negativos} colaborador(es) encerram o perÃ­odo com saldo final negativo.`);
  if (summary.ponto_a_justificar) alerts.push(`${summary.ponto_a_justificar} jornada(s) precisam de justificativa.`);
  return alerts.slice(0, 4);
}
