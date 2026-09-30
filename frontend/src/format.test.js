import test from "node:test";
import assert from "node:assert/strict";
import { filterProducts, topProducts } from "./format.js";

test("top products sorts revenue and quantity independently", () => {
  const products = [
    { product: "Laptop", quantity: 2, revenue: "200" },
    { product: "Mouse", quantity: 10, revenue: "50" },
  ];
  assert.equal(topProducts(products, "revenue")[0].product, "Laptop");
  assert.equal(topProducts(products, "quantity")[0].product, "Mouse");
  assert.equal(products[0].product, "Laptop");
});

test("chart data aggregates all remaining products into Other", () => {
  const products = Array.from({ length: 12 }, (_, index) => ({ product: `P${index}`, revenue: String(12 - index), quantity: 12 - index }));
  const result = topProducts(products, "revenue");
  assert.equal(result.length, 10);
  assert.deepEqual(result.at(-1), { product: "Other", value: 6 });
});

test("product search ignores surrounding spaces and case", () => {
  assert.deepEqual(filterProducts([{ product: "Laptop" }, { product: "Mouse" }], "  TOP "), [{ product: "Laptop" }]);
});
