import assert from "node:assert/strict";
import { test } from "node:test";
import { createEvaluationConfigCache } from "./evaluationConfigCache.js";

test("landing prefetch and evaluation reuse one metadata request", async () => {
  let calls=0, finish;
  const cache=createEvaluationConfigCache(()=>{calls++;return new Promise(resolve=>{finish=resolve;});});
  const landing=cache.load();
  const evaluation=cache.load();
  assert.equal(landing,evaluation);
  await Promise.resolve();
  const options={departments:[{code:"laboratory",applicable_colleges:["CCS"]}],colleges:[{code:"CCS"}]};
  finish(options);
  assert.deepEqual(await evaluation,options);
  assert.deepEqual(await cache.load(),options);
  assert.equal(calls,1);
});

test("metadata expires and failed prefetch can be retried", async () => {
  let time=0,calls=0;
  const cache=createEvaluationConfigCache(async()=>{calls++;if(calls===1)throw new Error("Offline");return {departments:[],colleges:[]};},{now:()=>time,ttlMs:60});
  await assert.rejects(cache.load(),/Offline/);
  await cache.load();
  await cache.load();
  assert.equal(calls,2);
  time=61;await cache.load();assert.equal(calls,3);
  await cache.load(true);assert.equal(calls,4);
});
test("saving settings can invalidate an in-flight public metadata snapshot",async()=>{
  const pending=[];
  const cache=createEvaluationConfigCache(()=>new Promise(resolve=>pending.push(resolve)));
  const old=cache.load();await Promise.resolve();cache.clear();
  const current=cache.load();await Promise.resolve();
  const newer={departments:[{id:2}],colleges:[]};pending[1](newer);await current;
  pending[0]({departments:[{id:1}],colleges:[]});await old;
  assert.deepEqual(await cache.load(),newer);
});
