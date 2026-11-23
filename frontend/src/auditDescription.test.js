import test from "node:test";
import assert from "node:assert/strict";
import { auditAction, auditTarget, auditChanges } from "./auditDescription.js";

test("audit labels explain the action and record",()=>{
  assert.equal(auditAction("backup_created"),"Downloaded encrypted backup");
  assert.equal(auditTarget("alerts:5"),"Intervention #5");
});
test("audit changes explain account status and roles without JSON syntax",()=>{
  const lines=auditChanges({detail:JSON.stringify({is_active:{before:[true],after:[false]},role:{before:["assistant"],after:["admin"]}})});
  assert.deepEqual(lines,["Status: Activated → Deactivated.","Role: Staff → Administrator."]);
});
test("audit changes resolve semester and service-area names",()=>{
  const lines=auditChanges({detail:JSON.stringify({active_cycle_id:{before:[1],after:[2]},department_id:{before:[],after:[3]}})},{cycles:[{id:1,label:"2026-2027 1st"},{id:2,label:"2026-2027 2nd"}],departments:[{id:3,name:"Registrar"}]});
  assert.deepEqual(lines,["Selected semester: 2026-2027 1st → 2026-2027 2nd.","Service area: Not recorded → Registrar."]);
});
test("audit free text is preserved as text",()=>{
  assert.deepEqual(auditChanges({detail:"<script>untrusted text</script>"}),["<script>untrusted text</script>"]);
});
