import test from "node:test";
import assert from "node:assert/strict";
import {
  CRITICALITY_WEIGHTS,
  classifyManagementSituation,
  rankCriticalEmployees,
  rankConformingEmployees,
  summarizeEmployees,
} from "./managerialMetrics.ts";
import type { DashboardRecord } from "./types.ts";

function record(
  employee_name: string,
  work_date: string,
  type: string,
  severity: DashboardRecord["severity"] = "OK",
  planned = 480,
): DashboardRecord {
  return {
    employee_name,
    work_date,
    weekday: "Seg",
    markings: {},
    marking_count: type === "PONTO_A_JUSTIFICAR" ? 0 : 2,
    expected_marking_count: planned ? 2 : null,
    total_minutes: planned,
    planned_minutes: planned,
    original_balance_minutes: 0,
    calculated_daily_balance_minutes: 0,
    observation: null,
    inconsistency_types: [type],
    severity,
    status: type === "SEM_JORNADA" ? "SEM_JORNADA" : "COM_JORNADA",
    is_planned_journey: planned > 0,
  };
}

test("criticality uses configured weights and excludes SEM_JORNADA", () => {
  assert.deepEqual(CRITICALITY_WEIGHTS, {
    PONTO_A_JUSTIFICAR: 5,
    MARCACAO_IMPAR: 4,
    MARCACOES_INCOMPLETAS: 2,
    MAIS_QUE_PREVISTO: 1,
    OK: 0,
    SEM_JORNADA: 0,
  });
  const [summary] = summarizeEmployees([
    record("Ana", "2026-08-01", "PONTO_A_JUSTIFICAR", "CRITICA"),
    record("Ana", "2026-08-02", "MARCACAO_IMPAR", "CRITICA"),
    record("Ana", "2026-08-03", "OK"),
    record("Ana", "2026-08-04", "SEM_JORNADA", "INFORMATIVO", 0),
  ]);
  assert.equal(summary.score_bruto, 9);
  assert.equal(summary.dias_com_jornada, 3);
  assert.equal(summary.score_normalizado, 3);
  assert.ok(Math.abs(summary.conformidade - 100 / 3) < 0.000001);
});

test("critical ranking prefers normalized score over raw occurrence count", () => {
  const rows = summarizeEmployees([
    ...Array.from({ length: 10 }, (_, index) => record("Bruno", `2026-08-${String(index + 1).padStart(2, "0")}`, index === 0 ? "PONTO_A_JUSTIFICAR" : "OK", index === 0 ? "CRITICA" : "OK")),
    ...Array.from({ length: 5 }, (_, index) => record("Carla", `2026-08-${String(index + 11).padStart(2, "0")}`, index < 2 ? "MARCACAO_IMPAR" : "OK", index < 2 ? "CRITICA" : "OK")),
  ]);
  const ranked = rankCriticalEmployees(rows);
  assert.equal(ranked[0].employee_name, "Carla");
  assert.equal(ranked[0].score_bruto, 8);
  assert.equal(ranked[0].score_normalizado, 1.6);
});

test("conforming ranking excludes employees below the configured minimum", () => {
  const rows = summarizeEmployees([
    ...Array.from({ length: 4 }, (_, index) => record("Short", `2026-08-${String(index + 1).padStart(2, "0")}`, "OK")),
    ...Array.from({ length: 5 }, (_, index) => record("Long", `2026-08-${String(index + 10).padStart(2, "0")}`, index === 4 ? "MARCACAO_IMPAR" : "OK", index === 4 ? "ATENCAO" : "OK")),
  ]);
  const ranked = rankConformingEmployees(rows);
  assert.deepEqual(ranked.map((row) => row.employee_name), ["Long"]);
});

test("reincidence requires critical occurrences on distinct dates", () => {
  const rows = summarizeEmployees([
    record("Ana", "2026-08-01", "PONTO_A_JUSTIFICAR", "CRITICA"),
    record("Ana", "2026-08-02", "MARCACAO_IMPAR", "CRITICA"),
    record("Bruno", "2026-08-01", "PONTO_A_JUSTIFICAR", "CRITICA"),
    record("Bruno", "2026-08-01", "MARCACAO_IMPAR", "CRITICA"),
  ]);
  assert.equal(rows.find((row) => row.employee_name === "Ana")?.reincidente, true);
  assert.equal(rows.find((row) => row.employee_name === "Bruno")?.reincidente, false);
  assert.equal(classifyManagementSituation(rows.find((row) => row.employee_name === "Ana")!), "REINCIDENTE");
});
