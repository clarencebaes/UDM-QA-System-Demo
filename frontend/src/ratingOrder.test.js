import test from "node:test";
import assert from "node:assert/strict";
import {sortRatingRows} from "./ratingOrder.js";
const rows=[{service_area:"Registrar",mean:3},{service_area:"Library",mean:5},{service_area:"Health",mean:null},{service_area:"Food",mean:3}];
test("rating order supports highest, lowest and service-area order without changing input",()=>{
  assert.deepEqual(sortRatingRows(rows,"highest").map(r=>r.service_area),["Library","Food","Registrar","Health"]);
  assert.deepEqual(sortRatingRows(rows,"lowest").map(r=>r.service_area),["Food","Registrar","Library","Health"]);
  assert.deepEqual(sortRatingRows(rows).map(r=>r.service_area),["Food","Health","Library","Registrar"]);
  assert.equal(rows[0].service_area,"Registrar");
});
