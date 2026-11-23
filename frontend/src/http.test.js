import assert from "node:assert/strict";
import { test } from "node:test";
import { fetchText } from "./http.js";

test("reads a successful response and preserves request options", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (_url, options) => {
    assert.equal(options.headers.Authorization, "Bearer synthetic-test-token");
    return new Response('{"ok":true}', { status: 200 });
  };
  try {
    const { response, text } = await fetchText("/synthetic", { headers: { Authorization: "Bearer synthetic-test-token" } });
    assert.equal(response.status, 200);
    assert.equal(text, '{"ok":true}');
  } finally { globalThis.fetch = original; }
});

test("a pending response stays pending without injecting a timeout or retrying", async () => {
  const original = globalThis.fetch;
  let calls = 0;
  let finish;
  globalThis.fetch = async (_url, options) => {
    calls++;
    assert.equal(options.method, "POST");
    assert.equal(options.signal, undefined);
    return { text: () => new Promise(resolve => { finish = resolve; }) };
  };
  try {
    const pending = fetchText("/synthetic", { method: "POST" });
    await Promise.resolve();
    assert.equal(calls, 1);
    finish("saved");
    assert.equal((await pending).text, "saved");
    assert.equal(calls, 1);
  } finally { globalThis.fetch = original; }
});

test("preserves network errors", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => { throw new TypeError("Network disconnected"); };
  try {
    await assert.rejects(fetchText("/synthetic"), /Network disconnected/);
  } finally { globalThis.fetch = original; }
});
