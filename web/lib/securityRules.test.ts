import test from "node:test";
import assert from "node:assert/strict";
import { isAdmin, isAllowedUpload, isSupportedPdf } from "./securityRules.ts";

test("ADMIN pode usar a área administrativa e VIEWER não", () => {
  assert.equal(isAdmin("ADMIN"), true);
  assert.equal(isAdmin("VIEWER"), false);
});

test("upload aceita somente PDF dentro do limite", () => {
  assert.equal(isSupportedPdf("jornada.PDF"), true);
  assert.equal(isSupportedPdf("jornada.exe"), false);
  assert.equal(isAllowedUpload("jornada.pdf", 1024, 2048), true);
  assert.equal(isAllowedUpload("jornada.pdf", 2049, 2048), false);
  assert.equal(isAllowedUpload("jornada.exe", 1024, 2048), false);
});
