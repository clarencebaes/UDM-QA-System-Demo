import assert from "node:assert/strict";
import { test } from "node:test";
import { buildInterventionView } from "./interventionPriority.js";

const now = Date.parse("2026-10-24T12:00:00Z");
const aspects = [{ code: "STAFF", name: "Staff Responsiveness" }, { code: "FAC", name: "Facility Conditions" }];
const threshold = { aspect_code: "STAFF", min_count: 3, window_days: 14, include_constructive: true };
const alert = { id: 1, aspect_code: "STAFF", aspect: "Staff Responsiveness", status: "new" };
const row = (id, department, sentiment = "negative", extra = {}) => ({ id, department, sentiment,
  aspect: "Staff Responsiveness", college: "CCS", comment: "Concern about the staff",
  created_at: "2026-10-24T10:00:00", ...extra });
const acrossAreas = [row(1, "Registrar"), row(2, "Campus Security"), row(3, "Library")];
const build = (rows = acrossAreas, thresholds = [threshold], alerts = [alert]) =>
  buildInterventionView(rows, aspects, thresholds, alerts, now);

function assertDashboardLinksToInterventions(view) {
  // Dashboard consumes view.feedback; Interventions consumes view.pairs.
  for (const feedback of view.feedback) {
    assert.ok(view.pairs.some((pair) => pair.service_area === feedback.department && pair.aspect === feedback.aspect));
  }
}

test("three negatives across three areas create one visible aspect and three contributing rows", () => {
  const view = build();
  assert.equal(view.aspects.length, 1);
  assert.equal(view.aspects[0].count, 3);
  assert.equal(view.aspects[0].area_count, 3);
  assert.equal(view.pairs.length, 3);
  assert.ok(view.pairs.every((pair) => pair.count === 1 && pair.aspect_count === 3 && pair.level === "medium"));
  assertDashboardLinksToInterventions(view);
});

test("two negatives plus one enabled constructive count across areas, not separately", () => {
  const rows = [row(1,"Registrar"), row(2,"Security"), row(3,"Library","constructive")];
  const view = build(rows);
  assert.equal(view.aspects[0].negative, 2);
  assert.equal(view.aspects[0].constructive, 1);
  assert.equal(view.feedback.length, 3);
  assertDashboardLinksToInterventions(view);
  const disabled = build(rows, [{...threshold, include_constructive: false}]);
  assert.equal(disabled.aspects.length, 0);
  assert.equal(disabled.pairs.length, 0);
  assert.equal(disabled.feedback.length, 0);
});

test("constructive-only alerts appear on both pages when enabled", () => {
  const view = build(acrossAreas.map((row) => ({...row, sentiment: "constructive"})));
  assert.equal(view.feedback.length, 3);
  assert.equal(view.aspects[0].negative, 0);
  assertDashboardLinksToInterventions(view);
});

test("disabled constructive rows do not appear when negatives already reach the threshold", () => {
  const view = build([...acrossAreas, row(4,"Another area","constructive")], [{...threshold, include_constructive:false}]);
  assert.equal(view.feedback.length, 3);
  assert.equal(view.pairs.length, 3);
  assert.equal(view.aspects[0].constructive, 0);
});

test("expiry excludes the same rows from Dashboard and Interventions", () => {
  const expired = build(acrossAreas.map((row) => ({...row, created_at: "2026-09-01T10:00:00Z"})));
  assert.deepEqual(expired, {aspects:[],pairs:[],feedback:[]});
  const partial = build([...acrossAreas, row(4,"Old area","negative",{created_at:"2026-09-01T00:00:00Z"})]);
  assert.equal(partial.feedback.length, 3);
  assert.equal(partial.pairs.length, 3);
});

test("threshold increases hide stale open alerts on both pages without altering records", () => {
  const view = build(acrossAreas, [{...threshold, min_count:4}]);
  assert.deepEqual(view, {aspects:[],pairs:[],feedback:[]});
  assert.equal(alert.status,"new");
});

test("row and detail priorities use the same aspect total at the high boundary", () => {
  const view = build([...acrossAreas, row(4,"Registrar"),row(5,"Registrar"),row(6,"Library")]);
  assert.equal(view.aspects[0].level,"high");
  assert.ok(view.pairs.every((pair) => pair.level === view.aspects[0].level && pair.aspect_count === 6));
});

test("completed alerts are not flagged; new, acknowledged and in-progress alerts are", () => {
  for (const status of ["resolved","completed"]) assert.equal(build(acrossAreas,[threshold],[{...alert,status}]).pairs.length,0);
  for (const status of ["new","acknowledged","in-progress"]) assert.equal(build(acrossAreas,[threshold],[{...alert,status}]).pairs.length,3);
});

test("different aspects cannot combine to breach a threshold", () => {
  const rows = [row(1,"A"),row(2,"B"),row(3,"C","negative",{aspect:"Facility Conditions"})];
  const view = build(rows,[threshold,{...threshold,aspect_code:"FAC"}],[alert,{...alert,id:2,aspect_code:"FAC"}]);
  assert.equal(view.pairs.length,0);
});

test("college filtering happens after campus-wide eligibility and cannot hide corresponding interventions", () => {
  const view = build(acrossAreas.map((row,i) => ({...row,college:i===0?"CAS":"CCS"})));
  const casFlagged = view.feedback.filter((row) => row.college==="CAS");
  assert.equal(casFlagged.length,1);
  assert.ok(view.pairs.some((pair) => pair.service_area===casFlagged[0].department));
});

test("UTC timestamps with and without offsets use the same inclusive window boundary", () => {
  const rows = [row(1,"A","negative",{created_at:"2026-10-10T12:00:00"}),
    row(2,"B","negative",{created_at:"2026-10-10T12:00:00Z"}),
    row(3,"C","negative",{created_at:"2026-10-10T20:00:00+08:00"})];
  assert.equal(build(rows).feedback.length,3);
});

test("missing thresholds, missing alerts, unknown aspects and invalid dates cannot invent alerts", () => {
  assert.equal(build(acrossAreas,[]).pairs.length,0);
  assert.equal(build(acrossAreas,[threshold],[]).pairs.length,0);
  assert.equal(build(acrossAreas.map((row) => ({...row,aspect:"Unknown"}))).pairs.length,0);
  assert.equal(build(acrossAreas.map((row) => ({...row,created_at:"bad-date"}))).pairs.length,0);
});
