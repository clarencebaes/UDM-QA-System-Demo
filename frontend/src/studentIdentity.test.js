import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { isValidStudentNumber, normalizeStudentNumber, isValidEmail } from "./studentIdentity.js";

const cases = JSON.parse(readFileSync(new URL("../../tests/fixtures/student-identity.json", import.meta.url), "utf8"));

test("student identifiers match the shared frontend/backend shape-only policy", () => {
  for (const item of cases) {
    assert.equal(isValidStudentNumber(item.value), item.valid, JSON.stringify(item.value));
    assert.equal(normalizeStudentNumber(item.value), item.normalized);
  }
});
test("normalization preserves leading zeros and does not rewrite digit groups", () => {
  assert.equal(normalizeStudentNumber(" 00-18-000 "), "00-18-000");
  assert.equal(normalizeStudentNumber("0018000"), "0018000");
  assert.equal(isValidStudentNumber("0018000"), false);
  assert.equal(normalizeStudentNumber(null), "");
});
test("institutional email checks remain in place", () => {
  assert.equal(isValidEmail("identity-test@udm.edu.ph"), true);
  assert.equal(isValidEmail("identity-test@example.com"), false);
});
