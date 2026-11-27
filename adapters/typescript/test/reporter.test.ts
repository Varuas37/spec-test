import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";
import { parseTestName, testName } from "../src/spec.js";

test("only a valid requirement tag qualifies as evidence", () => {
  expect(parseTestName(testName("QUEUE-001", "property", "stays bounded")))
    .toEqual({ specId: "QUEUE-001", kind: "property" });
  expect(parseTestName("[QUEUE-001|model-proof] unsupported kind")).toBeUndefined();
  expect(parseTestName("[unstructured|test] invalid ID")).toBeUndefined();
  expect(() => testName("QUEUE-001", "test", " ")).toThrow(TypeError);
});

test("actual Vitest exit and report distinguish pass, skip, setup failure, and expected failure", () => {
  const cli = fileURLToPath(new URL("../node_modules/vitest/vitest.mjs", import.meta.url));
  const result = spawnSync(process.execPath, [cli, "run", "--config", "fixtures/vitest.config.ts"],
    { encoding: "utf8", timeout: 10_000 });
  expect(result.error).toBeUndefined();
  expect(result.status, result.stderr).toBe(1);
  const report = JSON.parse(readFileSync(".vitest/spec-evidence-fixture.json", "utf8"));
  expect(report.schema_version).toBe(1);
  expect(report.checks).toHaveLength(5);
  expect(report.checks.map(({ status }: { status: string }) => status).sort())
    .toEqual(["failed", "passed", "skipped", "skipped", "unknown"]);
  expect(report.checks).toContainEqual(expect.objectContaining({
    spec_id: "QUEUE-001", kind: "test", runner: "vitest",
    name: expect.stringContaining("never enters test callback"), status: "failed",
  }));
  expect(report.checks).toContainEqual(expect.objectContaining({
    spec_id: "QUEUE-001", kind: "property", runner: "vitest", status: "passed",
  }));
}, 15_000);
