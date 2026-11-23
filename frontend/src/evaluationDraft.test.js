import test from "node:test";
import assert from "node:assert/strict";
import { readDraft, saveDraft, clearDraft, DRAFT_KEY } from "./evaluationDraft.js";
import { can, roleOf, ROLE_NAMES } from "./permissions.js";

test("a reload recovers identity, answers, comments and the current page without a server submission", () => {
  const values = new Map();
  const storage = {getItem: key => values.get(key), setItem: (key,value) => values.set(key,value), removeItem: key => values.delete(key)};
  const draft = {cycleId: 7, identity: {student_number: "26-01-123", institutional_email: "test@udm.edu.ph", college: "CAS"}, studentStatus: "regular", step: 3, ratings: {1: {rating_1: 4}}, comments: {1: "Helpful staff"}};
  assert.equal(saveDraft(draft, storage), true);
  assert.deepEqual(readDraft(storage), {...draft,version: 1});
  clearDraft(storage); assert.equal(readDraft(storage), null);
  storage.setItem(DRAFT_KEY, "bad json"); assert.equal(readDraft(storage), null);
  storage.setItem(DRAFT_KEY, JSON.stringify({...draft,version: 1,ratings: null})); assert.equal(readDraft(storage), null);
  assert.equal(saveDraft(draft, {setItem: () => {throw Error("Storage unavailable");}}), false);
});

test("navigation uses the four-role hierarchy and preserves legacy owner access", () => {
  assert.deepEqual(Object.keys(ROLE_NAMES), ["executive_director", "admin", "assistant", "viewer"]);
  assert.equal(roleOf({role: "super_admin"}), "executive_director");
  assert.equal(can("executive_director", "restore"), true);
  assert.equal(can("admin", "users"), true);
  assert.equal(can("admin", "restore"), false);
  assert.equal(can("assistant", "settings"), false);
  assert.equal(can("viewer", "feedback"), false);
  assert.equal(can("viewer", "reports"), true);
});
