export type DashboardRecord = {
  employee_name: string;
  work_date: string;
  weekday: string;
  markings: Record<string, string | null>;
  marking_count: number;
  expected_marking_count: number | null;
  total_minutes: number | null;
  planned_minutes: number | null;
  original_balance_minutes: number | null;
  calculated_daily_balance_minutes: number | null;
  observation: string | null;
  inconsistency_types: string[];
  severity: "OK" | "ATENCAO" | "CRITICA" | "INFORMATIVO";
  status: string;
  is_planned_journey: boolean;
};

export type DailyInconsistency = {
  total: number;
  ponto_a_justificar: number;
  marcacao_impar: number;
  marcacoes_incompletas: number;
  mais_que_previsto: number;
  ponto_sem_jornada: number;
};

export type EmployeeRankingRow = {
  employee_name: string;
  posicao: number;
  inconsistencias: number;
  criticas: number;
  atencao: number;
  registros_ok: number;
  dias_analisados: number;
  dias_com_jornada: number;
  conformidade: number;
  status: string;
  saldo_final: number | null;
  data_saldo_final: string | null;
  score_bruto: number;
  score_normalizado: number;
  pontos_a_justificar: number;
  marcacoes_impares: number;
  marcacoes_incompletas: number;
  mais_que_previsto: number;
  dias_criticos: number;
  ultima_ocorrencia: string | null;
  reincidente: boolean;
  situacao_gerencial: "CONFORME" | "BAIXA_ATENCAO" | "ATENCAO" | "CRITICO" | "REINCIDENTE";
};

export type EmployeeMetric = Omit<EmployeeRankingRow, "posicao" | "status" | "tem_saldo_final" | "critico"> & {
  status?: string;
  tem_saldo_final?: boolean;
  critico?: boolean;
};

export type DashboardSummary = {
  colaboradores: number;
  registros: number;
  dias_com_jornada: number;
  dias_sem_jornada: number;
  sem_marcacoes: number;
  marcacao_impar: number;
  marcacoes_incompletas: number;
  mais_que_previsto: number;
  ponto_sem_jornada: number;
  ponto_a_justificar: number;
  feriados_sem_jornada: number;
  conflito_jornada_evento: number;
  registros_ok: number;
  colaboradores_criticos: number;
  colaboradores_100_conformes: number;
  colaboradores_reincidentes: number;
  colaboradores_sem_critica: number;
  media_inconsistencias_por_colaborador: number;
  percentual_colaboradores_criticos: number;
  percentual_jornadas_ponto_a_justificar: number;
  distribuicao_criticidade: Record<string, number>;
  reincidentes: Array<{
    employee_name: string;
    dias_criticos: number;
    pontos_a_justificar: number;
    marcacoes_impares: number;
    ultima_ocorrencia: string | null;
    conformidade: number;
  }>;
  saldos_finais_negativos: number;
  taxa_conformidade: number;
  registros_com_expectativa_indisponivel: number;
  issue_counts: Record<string, number>;
  inconsistencias_por_dia: Record<string, DailyInconsistency>;
  distribuicao_horas_previstas: Record<string, number>;
  saldo_finais: Array<{
    employee_name: string;
    saldo_final: number | null;
    data_saldo_final: string | null;
    tem_saldo_final: boolean;
    critico: boolean;
  }>;
};

export type DashboardData = {
  metadata: {
    generated_at?: string;
    latest_update?: string;
    source?: string;
    source_pdf?: string;
    records?: number;
    employees?: number;
    pages?: number | null;
    period_start?: string | null;
    period_end?: string | null;
    unparsed_records?: number;
    errors?: string[];
    report_status?: "SUCCESS" | "PROCESSING" | "FAILED";
  };
  summary: DashboardSummary;
  rankings: {
    maiores_inconsistencias: EmployeeRankingRow[];
    melhores_conformidades: EmployeeRankingRow[];
    criterio_melhores_conformidades?: string;
  };
  readings: string[];
  alerts?: string[];
  comparison?: {
    available: boolean;
    period_start?: string | null;
    period_end?: string | null;
    taxa_conformidade?: { current: number; previous: number; delta: number };
    ponto_a_justificar?: { current: number; previous: number; deltaPercent: number };
    marcacao_impar?: { current: number; previous: number; deltaPercent: number };
    colaboradores_criticos?: { current: number; previous: number; delta: number };
  };
  records: DashboardRecord[];
  baseSummary?: DashboardSummary;
  pagination?: { page: number; pageSize: number; total: number; totalPages: number };
  availableEmployees?: string[];
  user?: { id: string; email: string; role: string; name: string | null };
};
