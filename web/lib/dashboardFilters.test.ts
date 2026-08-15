import test from "node:test";
import assert from "node:assert/strict";
import { deriveFilteredView, EMPTY_FILTERS, filterRecords } from "./dashboardFilters.ts";
import type { DashboardRecord } from "./types";

function record(name: string, date: string, planned: number, markings: number, type: string): DashboardRecord {
  return {
    employee_name: name, work_date: date, weekday: "Seg", markings: { entrada_1: markings ? "08:00" : null },
    marking_count: markings, expected_marking_count: planned > 0 ? planned > 240 ? 4 : 2 : null,
    total_minutes: markings ? planned : 0, planned_minutes: planned, original_balance_minutes: 0,
    calculated_daily_balance_minutes: 0, observation: null, inconsistency_types: [type],
    severity: type === "PONTO_A_JUSTIFICAR" || type === "MARCACAO_IMPAR" ? "CRITICA" : type === "SEM_JORNADA" ? "INFORMATIVO" : type === "OK" ? "OK" : "ATENCAO",
    status: type === "SEM_JORNADA" ? "SEM_JORNADA" : "COM_JORNADA", is_planned_journey: planned > 0,
  };
}

const records = [
  record("Ana Silva", "2026-08-08", 480, 0, "PONTO_A_JUSTIFICAR"),
  record("Ana Silva", "2026-08-09", 0, 0, "SEM_JORNADA"),
  record("Bruno Lima", "2026-08-08", 480, 3, "MARCACAO_IMPAR"),
  record("Carla Souza", "2026-08-10", 240, 2, "OK"),
];

test("PONTO_A_JUSTIFICAR exige carga positiva e zero batidas", () => {
  const filtered = filterRecords(records, { ...EMPTY_FILTERS, type: "PONTO_A_JUSTIFICAR" });
  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].planned_minutes! > 0, true);
  assert.equal(filtered[0].marking_count, 0);
});

test("SEM_JORNADA não entra na visão principal de inconsistências", () => {
  const view = deriveFilteredView(records);
  assert.equal(view.summary.feriados_sem_jornada, 1);
  assert.equal(view.summary.ponto_a_justificar, 1);
  assert.equal(view.summary.issue_counts.SEM_JORNADA, 1);
});

test("filtro parcial por colaborador e filtro por data", () => {
  assert.equal(filterRecords(records, { ...EMPTY_FILTERS, employeeQuery: "silv" }).length, 2);
  assert.equal(filterRecords(records, { ...EMPTY_FILTERS, selectedDate: "2026-08-08" }).length, 2);
});

test("limpar filtros restaura todos os registros", () => {
  assert.equal(filterRecords(records, EMPTY_FILTERS).length, records.length);
});

test("ranking filtrado preserva o detalhe do colaborador", () => {
  const view = deriveFilteredView(filterRecords(records, { ...EMPTY_FILTERS, employeeQuery: "Ana" }));
  assert.equal(view.rankings.maiores_inconsistencias[0].employee_name, "Ana Silva");
  assert.equal(view.summary.ponto_a_justificar, 1);
});

test("filtros combinados aplicam severidade, saldo, jornada e situação", () => {
  const filtered = filterRecords(records, {
    ...EMPTY_FILTERS,
    employeeQuery: "Ana",
    severity: "CRITICA",
    balance: "non_negative",
    plannedJourney: "8h",
    managementSituation: "CRITICO",
  });
  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].employee_name, "Ana Silva");
});

test("filtro somente críticos não considera SEM_JORNADA", () => {
  const filtered = filterRecords(records, { ...EMPTY_FILTERS, onlyCritical: true });
  assert.deepEqual(filtered.map((item) => item.inconsistency_types[0]), ["PONTO_A_JUSTIFICAR", "MARCACAO_IMPAR"]);
});
