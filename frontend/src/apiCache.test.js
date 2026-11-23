import test,{after} from "node:test";
import assert from "node:assert/strict";
import {createServer} from "vite";
const server=await createServer({configFile:false,server:{middlewareMode:true,hmr:false},appType:"custom",logLevel:"error"});
const {api,setSession,clearSession}=await server.ssrLoadModule("/src/api.js");
const originalFetch=globalThis.fetch,originalStorage=globalThis.localStorage;
const values=new Map();
globalThis.localStorage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};
after(async()=>{globalThis.fetch=originalFetch;globalThis.localStorage=originalStorage;await server.close();});

test("API cache invalidates after writes, account switches, and logout; identity checks stay fresh",async()=>{
  const calls=[];
  globalThis.fetch=async(url,options)=>{calls.push({url:String(url),...options});return new Response(JSON.stringify({request:calls.length}),{status:200});};
  setSession("synthetic-A",{role:"super_admin"});
  await Promise.all([api.departments(),api.departments()]);assert.equal(calls.length,1);
  await api.request("/qa/test",{method:"PATCH",body:"{}"});await api.departments();assert.equal(calls.length,3);
  setSession("synthetic-B",{role:"assistant"});await api.departments();assert.equal(calls.length,4);
  assert.equal(calls[3].headers.Authorization,"Bearer synthetic-B");
  await api.me();await api.me();assert.equal(calls.length,6);
  clearSession();await api.departments();assert.equal(calls.length,7);assert.equal(calls[6].headers.Authorization,undefined);
});
test("report previews and live availability are never cached; permission errors clear saved reads",async()=>{
  let calls=0,denied=false;
  globalThis.fetch=async()=>{calls++;return new Response(JSON.stringify(denied?{detail:"Unauthorized"}:{ok:true}),{status:denied?401:200});};
  setSession("synthetic-C",{role:"super_admin"});
  await api.surveyStatus();await api.surveyStatus();assert.equal(calls,2);
  await api.request("/qa/reports",{method:"POST",body:"{}"});await api.request("/qa/reports",{method:"POST",body:"{}"});assert.equal(calls,4);
  await api.departments();denied=true;await assert.rejects(api.me(),/Unauthorized/);
  denied=false;await api.departments();assert.equal(calls,7);
});
test("role changes under the same token clear previously authorized reads",async()=>{
  let calls=0;
  globalThis.fetch=async()=>new Response(JSON.stringify({request:++calls}),{status:200});
  setSession("synthetic-role",{role:"super_admin"});await api.departments();
  setSession("synthetic-role",{role:"assistant"});await api.departments();assert.equal(calls,2);
});
test("navigation prefetch respects roles and never issues writes or report previews",async()=>{
  const {prefetchPage}=await server.ssrLoadModule("/src/pagePrefetch.js");
  const calls=[];
  globalThis.fetch=async(url,options)=>{calls.push({url:String(url),method:options.method||"GET"});return new Response("{}",{status:200});};
  setSession("synthetic-viewer",{role:"viewer"});await prefetchPage("/qa/users");assert.equal(calls.length,0);
  await prefetchPage("/qa/reports");assert.equal(calls.length,3);assert.ok(calls.every(r=>r.method==="GET"));
  assert.ok(calls.every(r=>!r.url.endsWith("/qa/reports")));
  setSession("synthetic-staff",{role:"assistant"});await prefetchPage("/qa/alerts");
  assert.ok(calls.some(r=>r.url.includes("include_alerts=true")));assert.ok(calls.every(r=>r.method==="GET"));
});
