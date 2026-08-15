import type { DashboardRecord, EmployeeMetric } from "./types.ts";

export const CRITICALITY_WEIGHTS = {
  PONTO_A_JUSTIFICAR: 5,
  MARCACAO_IMPAR: 4,
  MARCACOES_INCOMPLETAS: 2,
  MAIS_QUE_PREVISTO: 1,
  OK: 0,
  SEM_JORNADA: 0,
} as const;

export const MINIMUM_CONFORMING_DAYS = 5;
export const REINCIDENCE_DAYS = 2;

const weightedTypes = new Set(Object.keys(CRITICALITY_WEIGHTS));
const isPlanned = (record: DashboardRecord) => record.is_planned_journey;
const isOk = (record: DashboardRecord) => record.inconsistency_types.includes("OK");
const isInconsistency = (record: DashboardRecord) => record.inconsistency_types.some((type) => type !== "OK" && type !== "SEM_JORNADA");

export function summarizeEmployees(records: DashboardRecord[]): EmployeeMetric[] {
  const grouped = new Map<string, DashboardRecord[]>();
  for (const record of records) grouped.set(record.employee_name, [...(grouped.get(record.employee_name) ?? []), record]);

  return [...grouped.entries()].map(([employee_name, employeeRecords]) => {
    const ordered = [...employeeRecords].sort((a, b) => a.work_date.localeCompare(b.work_date));
    const planned = ordered.filter(isPlanned);
    const inconsistencies = ordered.filter(isInconsistency);
    const criticalRecords = inconsistencies.filter((record) => record.severity === "CRITICA");
    const criticalDates = new Set(criticalRecords.map((record) => record.work_date));
    const records_ok = planned.filter(isOk).length;
    const score_bruto = ordered.reduce((total, record) => total + record.inconsistency_types.reduce((rowTotal, type) => totalForType(rowTotal, type), 0), 0);
    const dias_com_jornada = planned.length;
    const balances = ordered.filter((record) => record.original_balance_minutes !== null);
    const lastBalance = balances.at(-1);
    const conformidade = dias_com_jornada ? records_ok / dias_com_jornada * 100 : 0;
    const score_normalizado = dias_com_jornada ? score_bruto / dias_com_jornada : 0;

    return {
      employee_name,
      dias_analisados: dias_com_jornada,
      dias_com_jornada,
      registros_ok: records_ok,
      inconsistencias: inconsistencies.length,
      pontos_a_justificar: countType(ordered, "PONTO_A_JUSTIFICAR"),
      marcacoes_impares: countType(ordered, "MARCACAO_IMPAR"),
      marcacoes_incompletas: countType(ordered, "MARCACOES_INCOMPLETAS"),
      mais_que_previsto: countType(ordered, "MAIS_QUE_PREVISTO"),
      criticas: criticalRecords.length,
      atencao: inconsistencies.filter((record) => record.severity === "ATENCAO").length,
      conformidade,
      score_bruto,
      score_normalizado,
      saldo_final: lastBalance?.original_balance_minutes ?? null,
      data_saldo_final: lastBalance?.work_date ?? null,
      dias_criticos: criticalDates.size,
      ultima_ocorrencia: criticalRecords.at(-1)?.work_date ?? null,
      reincidente: criticalDates.size >= REINCIDENCE_DAYS,
      situacao_gerencial: "CONFORME",
    } satisfies EmployeeMetric;
  }).map((row) => ({ ...row, situacao_gerencial: classifyManagementSituation(row) }));
}

function totalForType(total: number, type: string) {
  return weightedTypes.has(type) ? CRITICALITY_WEIGHTS[type as keyof typeof CRITICALITY_WEIGHTS] : 0;
}

function countType(records: DashboardRecord[], type: string) {
  return records.reduce((count, record) => count + (record.inconsistency_types.includes(type) ? 1 : 0), 0);
}

export function classifyManagementSituation(row: Pick<EmployeeMetric, "conformidade" | "criticas" | "reincidente">): EmployeeMetric["situacao_gerencial"] {
  if (row.reincidente) return "REINCIDENTE";
  if (row.conformidade < 80 || row.criticas > 0) return "CRITICO";
  if (row.conformidade < 90) return "ATENCAO";
  if (row.conformidade < 100) return "BAIXA_ATENCAO";
  return "CONFORME";
}

export function rankCriticalEmployees(rows: EmployeeMetric[], limit = 20) {
  return [...rows]
    .sort((a, b) => b.score_normalizado - a.score_normalizado || b.score_bruto - a.score_bruto || b.criticas - a.criticas || a.employee_name.localeCompare(b.employee_name, "pt-BR"))
    .slice(0, limit)
    .map((row, index) => ({ ...row, posicao: index + 1 }));
}

export function rankConformingEmployees(rows: EmployeeMetric[], minimumDays = MINIMUM_CONFORMING_DAYS, limit = 20) {
  return rows
    .filter((row) => row.dias_com_jornada >= minimumDays)
    .sort((a, b) => b.conformidade - a.conformidade || a.score_normalizado - b.score_normalizado || b.dias_analisados - a.dias_analisados || a.employee_name.localeCompare(b.employee_name, "pt-BR"))
    .slice(0, limit)
    .map((row, index) => ({ ...row, posicao: index + 1 }));
}
