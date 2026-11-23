import assert from "node:assert/strict";
import { test } from "node:test";
import { SERVICE_AREAS } from "./serviceAreas.js";
import { isServiceAreaApplicable } from "./evaluationPolicy.js";

test("only the five specified colleges receive Laboratory and a 16-area evaluation", () => {
  for (const college of ["CCS", "CHS", "CAS", "CCJ", "CED"]) {
    const visible = SERVICE_AREAS.filter((area) => isServiceAreaApplicable(area, college));
    assert.equal(visible.length, 16, college);
    assert.equal(visible.filter((area) => area.code === "laboratory").length, 1);
  }
});

test("other colleges receive 15 areas without submitting a Laboratory placeholder", () => {
  for (const college of ["CBM", "CPPG", "NEW", ""]) {
    const visible = SERVICE_AREAS.filter((area) => isServiceAreaApplicable(area, college));
    assert.equal(visible.length, 15, college);
    assert.ok(visible.every((area) => area.code !== "laboratory"));
    assert.equal(visible.at(-1).code, "gender_development");
  }
});

test("API applicability metadata is honored and college casing is normalized", () => {
  assert.equal(isServiceAreaApplicable({ code: "laboratory", applicable_colleges: ["CCS"] }, " ccs "), true);
  assert.equal(isServiceAreaApplicable({ code: "laboratory", applicable_colleges: ["CCS"] }, "CAS"), false);
  assert.equal(isServiceAreaApplicable({ code: "library" }, "CBM"), true);
});
