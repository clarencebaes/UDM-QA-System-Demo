import test from "node:test";
import assert from "node:assert/strict";
import {mergeDashboardData} from "./mergeDashboardData.js";
test("parallel chart defaults cannot replace summary counts or language and sentiment totals",()=>{
  const summary={total_comments:12,by_college:[{college:"CAS",responses:3}],polarity_counts:{neutral:2},language_counts:{english:12},by_service_area:[]};
  const charts={total_comments:0,by_college:[],language_counts:{english:0},by_service_area:[{service_area:"Registrar",total:3}],by_aspect:[{aspect:"Processing Time",negative:2}]};
  const merged=mergeDashboardData(summary,charts);
  assert.equal(merged.total_comments,12);assert.deepEqual(merged.by_college,summary.by_college);
  assert.deepEqual(merged.language_counts,{english:12});assert.deepEqual(merged.by_service_area,charts.by_service_area);
  assert.equal(summary.by_service_area.length,0);
});
