import type { DashboardRecord, DailyInconsistency, EmployeeRankingRow } from "./types.ts";
import { rankConformingEmployees, rankCriticalEmployees, summarizeEmployees } from "./managerialMetrics.ts";

export const ACTIONABLE_TYPES = [
  "PONTO_A_JUSTIFICAR",
  "MARCACAO_IMPAR",
  "MARCACOES_INCOMPLETAS",
  "MAIS_QUE_PREVISTO",
  "PONTO_SEM_JORNADA",
] as const;

export type FilterState = {
  type: string | null;
  employeeQuery: string;
  dateFrom: string;
  dateTo: string;
  selectedDate: string | null;
  severity: string | null;
  status: string | null;
  onlyCritical: boolean;
  onlyRecurrent: boolean;
  onlyJustification: boolean;
  balance: "all" | "negative" | "non_negative";
  conformityRange: "all" | "100" | "90-99" | "80-89" | "below-80";
  plannedJourney: "all" | "4h" | "8h" | "other";
  managementSituation: string | null;
};

export const EMPTY_FILTERS: FilterState = {
  type: null,
  employeeQuery: "",
  dateFrom: "",
  dateTo: "",
  selectedDate: null,
  severity: null,
  status: null,
  onlyCritical: false,
  onlyRecurrent: false,
  onlyJustification: false,
  balance: "all",
  conformityRange: "all",
  plannedJourney: "all",
  managementSituation: null,
};

export function filtersFromSearchParams(params: URLSearchParams): FilterState {
  const value = (key: string) => params.get(key) || null;
  const balance = value("balance");
  const conformityRange = value("conformity");
  const plannedJourney = value("journey");
  return {
    type: value("type"),
    employeeQuery: params.get("employee") ?? "",
    dateFrom: params.get("from") ?? "",
    dateTo: params.get("to") ?? "",
    selectedDate: value("date"),
    severity: value("severity"),
    status: value("status"),
    onlyCritical: params.get("critical") === "1",
    onlyRecurrent: params.get("recurrent") === "1",
    onlyJustification: params.get("justification") === "1",
    balance: balance === "negative" || balance === "non_negative" ? balance : "all",
    conformityRange: conformityRange === "100" || conformityRange === "90-99" || conformityRange === "80-89" || conformityRange === "below-80" ? conformityRange : "all",
    plannedJourney: plannedJourney === "4h" || plannedJourney === "8h" || plannedJourney === "other" ? plannedJourney : "all",
    managementSituation: value("situation"),
  };
}

const hasType = (record: DashboardRecord, type: string) => record.inconsistency_types.includes(type);
const isPlanned = (record: DashboardRecord) => record.is_planned_journey;
const isOk = (record: DashboardRecord) => hasType(record, "OK");
const isActionable = (record: DashboardRecord) => record.inconsistency_types.some((type) => ACTIONABLE_TYPES.includes(type as typeof ACTIONABLE_TYPES[number]));

export function filterRecords(records: DashboardRecord[], filters: FilterState): DashboardRecord[] {
  const query = filters.employeeQuery.trim().toLocaleLowerCase("pt-BR");
  const metrics = new Map(summarizeEmployees(records).map((row) => [row.employee_name, row]));
  return records.filter((record) => {
    if (filters.type && !hasType(record, filters.type)) return false;
    if (query && !record.employee_name.toLocaleLowerCase("pt-BR").includes(query)) return false;
    if (filters.dateFrom && record.work_date < filters.dateFrom) return false;
    if (filters.dateTo && record.work_date > filters.dateTo) return false;
    if (filters.selectedDate && record.work_date !== filters.selectedDate) return false;
    if (filters.severity && record.severity !== filters.severity) return false;
    if (filters.status && record.status !== filters.status) return false;
    if (filters.onlyCritical && (record.severity !== "CRITICA" || !isActionable(record))) return false;
    if (filters.onlyJustification && !hasType(record, "PONTO_A_JUSTIFICAR")) return false;
    if (filters.balance === "negative" && !(record.original_balance_minutes !== null && record.original_balance_minutes < 0)) return false;
    if (filters.balance === "non_negative" && (record.original_balance_minutes !== null && record.original_balance_minutes < 0)) return false;
    if (filters.plannedJourney !== "all") {
      const hours = record.planned_minutes === null ? null : record.planned_minutes / 60;
      if (filters.plannedJourney === "4h" && hours !== 4) return false;
      if (filters.plannedJourney === "8h" && hours !== 8) return false;
      if (filters.plannedJourney === "other" && (hours === null || hours === 4 || hours === 8)) return false;
    }
    const employee = metrics.get(record.employee_name);
    if (!employee) return false;
    if (filters.onlyRecurrent && !employee.reincidente) return false;
    if (filters.managementSituation && employee.situacao_gerencial !== filters.managementSituation) return false;
    if (filters.conformityRange !== "all") {
      const rate = employee.conformidade;
      const matchesRange = filters.conformityRange === "100" ? rate === 100 : filters.conformityRange === "90-99" ? rate >= 90 && rate < 100 : filters.conformityRange === "80-89" ? rate >= 80 && rate < 90 : rate < 80;
      if (!matchesRange) return false;
    }
    return true;
  });
}

function dailyRows(records: DashboardRecord[]): Record<string, DailyInconsistency> {
  const result: Record<string, DailyInconsistency> = {};
  for (const record of records) {
    const row = result[record.work_date] ?? {
      total: 0,
      ponto_a_justificar: 0,
      marcacao_impar: 0,
      marcacoes_incompletas: 0,
      mais_que_previsto: 0,
      ponto_sem_jornada: 0,
    };
    for (const type of ACTIONABLE_TYPES) {
      if (hasType(record, type)) {
        const key = type.toLocaleLowerCase() as keyof DailyInconsistency;
        row[key] += 1;
        row.total += 1;
      }
    }
    result[record.work_date] = row;
  }
  return Object.fromEntries(Object.entries(result).sort(([a], [b]) => a.localeCompare(b)));
}

function employeeRows(records: DashboardRecord[]): EmployeeRankingRow[] {
  return summarizeEmployees(records).map((row) => ({
    ...row,
    posicao: 0,
    status: row.situacao_gerencial,
  }));
}

export function buildRankings(records: DashboardRecord[], limit = 20, minimumDays = 5) {
  const summaries = employeeRows(records);
  const negative = rankCriticalEmployees(summaries, limit);
  const positive = rankConformingEmployees(summaries, minimumDays, limit);
  return {
    maiores_inconsistencias: negative,
    melhores_conformidades: positive,
  };
}

export function deriveFilteredView(records: DashboardRecord[]) {
  const issueCounts: Record<string, number> = {};
  records.forEach((record) => record.inconsistency_types.forEach((type) => { issueCounts[type] = (issueCounts[type] ?? 0) + 1; }));
  const planned = records.filter(isPlanned);
  const ok = planned.filter(isOk).length;
  const summaries = employeeRows(records);
  const finalNegative = summaries.filter((row) => row.saldo_final !== null && row.saldo_final < 0).length;
  const criticalEmployees = summaries.filter((row) => row.criticas > 0).length;
  const recurrent = summaries.filter((row) => row.reincidente);
  const distribution = summaries.reduce<Record<string, number>>((result, row) => {
    result[row.situacao_gerencial] = (result[row.situacao_gerencial] ?? 0) + 1;
    return result;
  }, {});
  const recurrentRows = recurrent.map((row) => ({ employee_name: row.employee_name, dias_criticos: row.dias_criticos, pontos_a_justificar: row.pontos_a_justificar, marcacoes_impares: row.marcacoes_impares, ultima_ocorrencia: row.ultima_ocorrencia, conformidade: row.conformidade })).sort((a, b) => b.dias_criticos - a.dias_criticos || a.employee_name.localeCompare(b.employee_name, "pt-BR"));
  const byHours: Record<string, number> = {};
  records.forEach((record) => {
    const hours = record.planned_minutes === null ? "" : `${String(Math.floor(record.planned_minutes / 60)).padStart(2, "0")}:${String(record.planned_minutes % 60).padStart(2, "0")}`;
    byHours[hours] = (byHours[hours] ?? 0) + 1;
  });
  return {
    records,
    summary: {
      colaboradores: new Set(records.map((record) => record.employee_name)).size,
      registros: records.length,
      dias_com_jornada: planned.length,
      dias_sem_jornada: records.length - planned.length,
      sem_marcacoes: issueCounts.PONTO_A_JUSTIFICAR ?? 0,
      ponto_a_justificar: issueCounts.PONTO_A_JUSTIFICAR ?? 0,
      feriados_sem_jornada: issueCounts.SEM_JORNADA ?? 0,
      marcacao_impar: issueCounts.MARCACAO_IMPAR ?? 0,
      marcacoes_incompletas: issueCounts.MARCACOES_INCOMPLETAS ?? 0,
      mais_que_previsto: issueCounts.MAIS_QUE_PREVISTO ?? 0,
      ponto_sem_jornada: issueCounts.PONTO_SEM_JORNADA ?? 0,
      registros_ok: ok,
      colaboradores_criticos: criticalEmployees,
      colaboradores_100_conformes: summaries.filter((row) => row.conformidade === 100 && row.dias_com_jornada > 0).length,
      colaboradores_reincidentes: recurrent.length,
      colaboradores_sem_critica: summaries.filter((row) => row.criticas === 0).length,
      media_inconsistencias_por_colaborador: summaries.length ? summaries.reduce((total, row) => total + row.inconsistencias, 0) / summaries.length : 0,
      percentual_colaboradores_criticos: summaries.length ? criticalEmployees / summaries.length * 100 : 0,
      percentual_jornadas_ponto_a_justificar: planned.length ? (issueCounts.PONTO_A_JUSTIFICAR ?? 0) / planned.length * 100 : 0,
      distribuicao_criticidade: distribution,
      reincidentes: recurrentRows,
      saldos_finais_negativos: finalNegative,
      taxa_conformidade: planned.length ? ok / planned.length * 100 : 0,
      issue_counts: issueCounts,
      inconsistencias_por_dia: dailyRows(records),
      distribuicao_horas_previstas: byHours,
    },
    rankings: buildRankings(records),
  };
}
