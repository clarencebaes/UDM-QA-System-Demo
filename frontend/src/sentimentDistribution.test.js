import test from "node:test";
import assert from "node:assert/strict";
import { sentimentDistribution } from "./sentimentDistribution.js";

test("four saved categories retain Constructive without adding overlapping polarity counts",()=>{
  const result=sentimentDistribution({positive:9,constructive:2,negative:16,neutral:3,polarity_counts:{positive:10,negative:17,neutral:3,unclassified:0},feedback_types:{constructive:2}});
  assert.deepEqual(result,{positive:9,constructive:2,negative:16,neutral:3,unclassified:0});
  assert.equal(Object.values(result).reduce((a,b)=>a+b,0),30);
});
test("reports and dashboard use the same categories, including empty selections",()=>{
  assert.deepEqual(sentimentDistribution({sentiment:{positive:9,constructive:2,negative:16,neutral:3,unclassified:0}}),sentimentDistribution({positive:9,constructive:2,negative:16,neutral:3,unclassified:0}));
  assert.deepEqual(sentimentDistribution(),{positive:0,constructive:0,negative:0,neutral:0,unclassified:0});
});
