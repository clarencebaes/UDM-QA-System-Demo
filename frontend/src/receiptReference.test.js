import test from "node:test";
import assert from "node:assert/strict";
import {referenceWasShown, markReferenceShown} from "./receiptReference.js";

test("the reference is shown once per protected receipt, without hiding another semester's reference", () => {
  const values = new Map();
  const storage = {getItem: key => values.get(key), setItem: (key,value) => values.set(key,value)};
  assert.equal(referenceWasShown("receipt-A",storage), false);
  markReferenceShown("receipt-A",storage);
  assert.equal(referenceWasShown("receipt-A",storage), true);
  assert.equal(referenceWasShown("receipt-B",storage), false);
  assert.equal(referenceWasShown("receipt-A", {getItem: () => {throw Error("Unavailable");}}), true);
});
