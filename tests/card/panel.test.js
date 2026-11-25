// Pure functions of the panel "eQ-3 MAX!" (order of areas and devices).
import { test } from "node:test";
import assert from "node:assert/strict";

// The module defines its element at load: stand-ins for the browser.
globalThis.HTMLElement = class {};
globalThis.customElements = { get: () => undefined, define: () => {} };
const { applyOrder, moveKey } = await import("../../custom_components/eq3_max/frontend/eq3-max-panel.js");

const key = (item) => item.id;
const items = [{ id: "bad" }, { id: "flur" }, { id: "kueche" }, { id: "" }];

test("applyOrder: without a stored order the default stays", () => {
  assert.equal(applyOrder(items, key, undefined), items);
  assert.equal(applyOrder(items, key, []), items);
});

test("applyOrder: stored keys first, new ones behind in default order, gone ones ignored", () => {
  const result = applyOrder(items, key, ["kueche", "weg", "bad"]);
  assert.deepEqual(result.map(key), ["kueche", "bad", "flur", ""]);
});

test("moveKey: one place forward or back, nothing at the ends or for an unknown key", () => {
  const keys = ["a", "b", "c"];
  assert.deepEqual(moveKey(keys, "b", -1), ["b", "a", "c"]);
  assert.deepEqual(moveKey(keys, "b", +1), ["a", "c", "b"]);
  assert.equal(moveKey(keys, "a", -1), keys);
  assert.equal(moveKey(keys, "c", +1), keys);
  assert.equal(moveKey(keys, "x", +1), keys);
  assert.deepEqual(keys, ["a", "b", "c"]);
});
