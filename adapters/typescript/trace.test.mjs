import { test } from "node:test";
import assert from "node:assert/strict";
import { scan } from "./trace.mjs";

test("preserves multiple ADR rules and distinct class, instance and static members", () => {
  const links = scan("queue.ts", `
/**
 * @specTestImplements QUEUE-001
 * @specTestImplements LIMIT-002
 */
export class Queue {
  /** @specTestImplements QUEUE-003 */
  add() {}
  /** @specTestImplements QUEUE-004 */
  static add() {}
}
/** @specTestImplements QUEUE-005 */
export function create() {}
/** @specTestImplements QUEUE-006 */
export const open = () => new Queue();
`, () => false);
  assert.deepEqual(links.map(({spec_id, symbol}) => [spec_id, symbol]), [
    ["QUEUE-001", "Queue"], ["LIMIT-002", "Queue"], ["QUEUE-003", "Queue#add"],
    ["QUEUE-004", "Queue.add"], ["QUEUE-005", "create"], ["QUEUE-006", "open"],
  ]);
  assert.equal(links[0].line, 3);
});

test("indexes a real imported test alias but not calls to foreign helpers", () => {
  const source = `
import {specTest as check} from "./spec.js";
import {specTest as unrelated} from "./other.js";
check("QUEUE-001", "does not grow", () => {});
unrelated("BOGUS-001", "not our helper", () => {});
`;
  const [testLink, ...rest] = scan("check.ts", source, p => p === "./spec.js");
  assert.equal(testLink.role, "verifies");
  assert.equal(testLink.symbol, "specTest: does not grow");
  assert.equal(rest.length, 0);
});

test("rejects malformed or duplicate declarations rather than dropping links", () => {
  for (const source of [
    "/** @specTestImplements queue-1 */\nfunction f() {}",
    "/** @specTestImplements QUEUE-1 */\nconst f = 1, g = 2;",
    "/**\n * @specTestImplements QUEUE-1\n * @specTestImplements QUEUE-1\n */\nfunction f() {}",
    'import {specTest} from "./spec.js";\nspecTest(id, "title", fn);',
  ]) {
    assert.throws(() => scan("bad.ts", source, () => true));
  }
});
