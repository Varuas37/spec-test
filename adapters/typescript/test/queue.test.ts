import fc from "fast-check";
import { expect } from "vitest";
import { contract, ContractError } from "../src/contract.js";
import { enqueue } from "../src/queue.js";
import { specProperty, specTest } from "../src/spec.js";

specTest("QUEUE-001", "handles zero, full, and malformed queue states", () => {
  expect(enqueue(0, 0)).toEqual({ ok: true, accepted: false, len: 0 });
  expect(enqueue(254, 255)).toEqual({ ok: true, accepted: true, len: 255 });
  expect(enqueue(255, 255)).toEqual({ ok: true, accepted: false, len: 255 });
  expect(enqueue(255, 254)).toEqual({ ok: false });
  expect(() => enqueue(-1, 0)).toThrow(ContractError);
  expect(() => enqueue(0, 256)).toThrow(ContractError);
  expect(() => enqueue(0.5, 1)).toThrow(ContractError);
  expect(() => enqueue(0, Number.NaN)).toThrow(ContractError);
});

specProperty("QUEUE-001", "the real implementation respects capacity and admits exactly when possible", () => {
  const u8 = fc.integer({ min: 0, max: 255 });
  fc.assert(fc.property(u8, u8, (len, capacity) => {
    const result = enqueue(len, capacity);
    if (!result.ok) {
      expect(len).toBeGreaterThan(capacity);
      return;
    }
    expect(len).toBeLessThanOrEqual(capacity);
    expect(result.len).toBeLessThanOrEqual(capacity);
    expect(result.accepted).toBe(len < capacity);
    expect(result.len - len).toBe(result.accepted ? 1 : 0);
  }), { numRuns: 512 });
});

specTest("QUEUE-001", "runtime contracts reject input before executing and catch a bad result", () => {
  let calls = 0;
  const broken = contract("QUEUE-001", (n: number) => { calls += 1; return n + 1; }, {
    requires: n => n >= 0,
    ensures: (result, n) => result === n,
  });
  expect(() => broken(-1)).toThrow("QUEUE-001: contract violation (requires)");
  expect(calls).toBe(0);
  expect(() => broken(1)).toThrow("QUEUE-001: contract violation (ensures)");
  expect(calls).toBe(1);
});

specTest("QUEUE-001", "enumerates the finite u8 input domain on the real implementation", () => {
  for (let len = 0; len <= 255; len++) {
    for (let capacity = 0; capacity <= 255; capacity++) {
      const result = enqueue(len, capacity);
      if (len > capacity) {
        if (result.ok) throw new Error(`accepted malformed state: ${len}/${capacity}`);
        continue;
      }
      const admitted = len < capacity;
      if (!result.ok || result.accepted !== admitted || result.len !== len + (admitted ? 1 : 0)) {
        throw new Error(`wrong admission outcome: ${len}/${capacity}`);
      }
    }
  }
});
