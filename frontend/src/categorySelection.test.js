import test from "node:test";
import assert from "node:assert/strict";
import { toggleCategories } from "./categorySelection.js";
import { sentimentDistribution } from "./sentimentDistribution.js";

test("categories combine, deselect individually and reset to All",()=>{
  let selection=toggleCategories("all","positive");
  selection=toggleCategories(selection,"negative");
  assert.equal(selection,"negative,positive");
  assert.equal(toggleCategories(selection,"positive"),"negative");
  assert.equal(toggleCategories("negative","negative"),"all");
  assert.equal(toggleCategories(selection,"all"),"all");
});

test("unclassified written comments fill the chart gap without counting placeholders",()=>{
  const counts=sentimentDistribution({positive:52,negative:164,constructive:55,neutral:5,unclassified_comments:7,no_substantive_comments:153});
  assert.equal(Object.values(counts).reduce((a,b)=>a+b,0),283);
  assert.equal(counts.unclassified,7);
  assert.deepEqual(sentimentDistribution({sentiment:counts}),counts);
});
