import test from "node:test";
import assert from "node:assert/strict";
import {reportTitle,reportDescription} from "./reportDescription.js";
const data={respondents:12,evaluations:180,completed_submissions:12,ratings:[{mean:3.5},{mean:4.5}],concerns:[{},{}],intervention_summary:{awaiting:1,approved:2,completed:3},completed_interventions:[{},{}]};
test("report title follows chosen outputs",()=>{
  assert.equal(reportTitle(["completed"]),"Completed Intervention Report");
  assert.equal(reportTitle(["ratings","completed"]),"Student Evaluation and Intervention Report");
});
test("report description uses actual selected data",()=>{
  const text=reportDescription(data,["participation","ratings"]);
  assert.match(text,/12 distinct students/);assert.match(text,/180 service-area/);assert.match(text,/3.50 to 4.50/);
  assert.doesNotMatch(text,/completed campus-wide interventions/);
});
test("completed-only output explains its independent campus-wide scope",()=>{
  const text=reportDescription(data,["completed"]);
  assert.match(text,/2 completed campus-wide interventions/);assert.doesNotMatch(text,/180/);
});
test("language and sentiment output use scoped dimension counts",()=>{
  const text=reportDescription({comments:7,sentiment:{positive:1,constructive:1,negative:3,neutral:2},polarity_counts:{positive:2,negative:3,neutral:2},feedback_types:{constructive:1},language_counts:{english:3,tagalog:2,taglish:1,undetermined:1}},["sentiment","language"]);
  assert.match(text,/2 neutral/);assert.match(text,/1 constructive/);assert.match(text,/1 positive/);
  assert.match(text,/3 English, 2 Tagalog and 1 Taglish; 1 unclassified/);
});
