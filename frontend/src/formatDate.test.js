import test from "node:test";
import assert from "node:assert/strict";
import { formatDate, philippineDay } from "./formatDate.js";
test("UTC API timestamps with or without offsets use Philippine time across the midnight boundary",()=>{
  assert.equal(formatDate("2026-10-30T17:25:00"),formatDate("2026-10-30T17:25:00Z"));
  assert.equal(formatDate("2026-10-30T17:25:00Z"),formatDate("2026-10-31T01:25:00+08:00"));
  assert.equal(philippineDay("2026-10-30T17:25:00"),"2026-10-31");
  assert.equal(formatDate("invalid"),"—");
});
