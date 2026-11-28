import { contract } from "./contract.js";

export type EnqueueResult =
  | { ok: false }
  | { ok: true; accepted: boolean; len: number };

const u8 = (value: number) => Number.isInteger(value) && value >= 0 && value <= 255;

// QUEUE-001 models the admission boundary, not queue storage or concurrency.
export const enqueue = contract(
  "QUEUE-001",
  (len: number, capacity: number): EnqueueResult => {
    if (len > capacity) return { ok: false };
    const accepted = len < capacity;
    return { ok: true, accepted, len: accepted ? len + 1 : len };
  },
  {
    requires: (len, capacity) => u8(len) && u8(capacity),
    ensures: (result, len, capacity) =>
      len > capacity
        ? !result.ok
        : result.ok && result.len <= capacity
          && result.accepted === (len < capacity)
          && result.len === len + Number(result.accepted),
  },
);
