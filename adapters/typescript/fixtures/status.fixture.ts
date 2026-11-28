import { beforeEach, describe, test } from "vitest";
import { specProperty, specTest, testName } from "../src/spec.js";

specProperty("QUEUE-001", "passing property", () => {});
test.skip(testName("QUEUE-001", "test", "skipped before executing"), () => {});
test.todo(testName("QUEUE-001", "test", "declared but not implemented"));
test.fails(testName("QUEUE-001", "test", "expected failure is not passing evidence"), () => {
  throw new Error("intentional expected failure");
});

describe("setup failure", () => {
  beforeEach(() => { throw new Error("intentional failure before test callback"); });
  specTest("QUEUE-001", "never enters test callback", () => {});
});
