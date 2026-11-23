import assert from "node:assert/strict";
import { test } from "node:test";
import { participationSummary } from "./participation.js";

test("participation uses enrolled students as its denominator", () => {
  assert.deepEqual(participationSummary(3, 700), {remaining:697, denominator:700, valid:true});
  assert.equal(3 / participationSummary(3, 700).denominator * 100, 3 / 700 * 100);
  assert.deepEqual(participationSummary(100, 100), {remaining:0, denominator:100, valid:true});
});

test("unknown or inconsistent enrollment cannot produce a misleading percentage", () => {
  assert.equal(participationSummary(3, null).valid, false);
  assert.equal(participationSummary(3, 2).valid, false);
  assert.equal(participationSummary(0, 100).valid, true);
});
