import test from "node:test";
import assert from "node:assert/strict";
import { readTheme, saveTheme } from "./theme.js";

test("theme defaults to light and persists dark preference", (t) => {
  const values = new Map();
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
  t.after(() => { delete globalThis.localStorage; });
  assert.equal(readTheme(), "light");
  saveTheme("dark");
  assert.equal(readTheme(), "dark");
});
