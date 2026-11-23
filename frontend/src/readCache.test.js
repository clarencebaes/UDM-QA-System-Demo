import test from "node:test";
import assert from "node:assert/strict";
import {createReadCache,readKey} from "./readCache.js";

test("parallel reads share a request and recent filters reuse their response",async()=>{
  let calls=0,clock=0;
  const cache=createReadCache({now:()=>clock,ttlMs:20});
  const fetcher=async()=>({request:++calls});
  const [a,b]=await Promise.all([cache.read("CAS",fetcher),cache.read("CAS",fetcher)]);
  assert.equal(calls,1);assert.equal(a,b);
  await cache.read("CCS",fetcher);assert.equal((await cache.read("CAS",fetcher)).request,1);
  clock=21;await cache.read("CAS",fetcher);assert.equal(calls,3);
});
test("failed reads can retry and bounded storage evicts old entries",async()=>{
  const cache=createReadCache({maxEntries:2});
  await assert.rejects(cache.read("failed",()=>{throw Error("offline");}),/offline/);
  assert.equal(await cache.read("failed",()=>1),1);
  await cache.read("second",()=>2);await cache.read("third",()=>3);
  assert.equal(await cache.read("failed",()=>4),4);
});
test("clearing pending reads prevents old results rewarming a new session or saved state",async()=>{
  const cache=createReadCache();let finish;
  const old=cache.read("same",()=>new Promise(resolve=>{finish=resolve;}));
  await Promise.resolve();cache.clear();
  assert.equal(await cache.read("same",()=>"new"),"new");
  finish("old");assert.equal(await old,"old");
  assert.equal(await cache.read("same",()=>"wrong"),"new");
});
test("scope and all filter values stay separate while parameter ordering is normalized",()=>{
  assert.equal(readKey("/qa/dashboard?college=CAS&cycle_id=1","A"),readKey("/qa/dashboard?cycle_id=1&college=CAS","A"));
  assert.notEqual(readKey("/qa/dashboard?college=CAS","A"),readKey("/qa/dashboard?college=CCS","A"));
  assert.notEqual(readKey("/qa/dashboard","A"),readKey("/qa/dashboard","B"));
});
