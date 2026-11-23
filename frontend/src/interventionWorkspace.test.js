import test from "node:test";
import assert from "node:assert/strict";
import {loadInterventionWorkspace} from "./interventionWorkspace.js";
test("one coherent response supplies newly created alerts without a second request",async()=>{
  const payload={pairs:[{alert_id:7}],alerts:[{id:7,status:"new"}]};
  const result=await loadInterventionWorkspace({interventionWorkspace:async()=>payload,alerts:()=>{throw Error("Must not fetch a racing alert snapshot");}});
  assert.equal(result.alerts[0].id,result.interventions.pairs[0].alert_id);
});
test("older backends fetch alerts after intervention synchronization completes",async()=>{
  let synchronized=false;
  const result=await loadInterventionWorkspace({interventionWorkspace:async()=>{synchronized=true;return {pairs:[{alert_id:7}]};},alerts:async()=>{assert.equal(synchronized,true);return [{id:7}];}});
  assert.equal(result.alerts[0].id,7);
});
