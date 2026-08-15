import { DashboardData } from "./types";

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-");
  return year && month && day ? `${day}/${month}/${year}` : value;
}

export function getMetrics(data: DashboardData) {
  const summary = data.summary;
  const byType = Object.entries(summary.issue_counts)
    .filter(([type]) => type !== "OK" && type !== "SEM_JORNADA")
    .sort((a, b) => b[1] - a[1]);
  const byDay = Object.entries(summary.inconsistencias_por_dia);
  const byHours = Object.entries(summary.distribuicao_horas_previstas);
  return {
    employees: summary.colaboradores,
    planned: summary.dias_com_jornada,
    noMarks: summary.ponto_a_justificar,
    noJourney: summary.feriados_sem_jornada,
    oddMarks: summary.marcacao_impar,
    incompleteMarks: summary.marcacoes_incompletas,
    moreThanPlanned: summary.mais_que_previsto,
    noJourneyMarks: summary.ponto_sem_jornada,
    criticalEmployees: summary.colaboradores_criticos,
    negativeBalances: summary.saldos_finais_negativos,
    ok: summary.registros_ok,
    rate: summary.taxa_conformidade,
    byType,
    byDay,
    byHours,
  };
}
