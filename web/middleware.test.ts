import test from "node:test";
import assert from "node:assert/strict";
import { isPublicPath } from "./lib/middlewarePolicy.ts";

test("Workflow internal endpoints bypass authentication middleware", () => {
  assert.equal(isPublicPath("/.well-known/workflow/v1/flow"), true);
  assert.equal(isPublicPath("/.well-known/workflow/v1/step"), true);
  assert.equal(isPublicPath("/api/admin/report-status"), false);
});

test("Scheduled automation endpoints bypass session middleware", () => {
  assert.equal(isPublicPath("/api/automation/report"), true);
  assert.equal(isPublicPath("/api/automation/absence"), true);
  assert.equal(isPublicPath("/api/automation/delay"), true);
});
