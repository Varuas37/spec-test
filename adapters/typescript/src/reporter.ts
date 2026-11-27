import { mkdirSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import type { Reporter } from "vitest/node";
import { parseTestName, type TestKind } from "./spec.js";

type Status = "passed" | "failed" | "skipped" | "unknown";
type Check = {
  spec_id: string;
  kind: TestKind;
  runner: "vitest";
  name: string;
  status: Status;
};

export default class SpecReporter implements Reporter {
  private readonly output: string;
  private readonly tmp: string;

  constructor(path = ".vitest/spec-evidence.json") {
    this.output = resolve(path);
    this.tmp = `${this.output}.${process.pid}.tmp`;
  }

  onTestRunStart(): void {
    // A failed or killed run must not leave a previous run's success evidence.
    rmSync(this.output, { force: true });
  }

  onTestRunEnd(...[modules, errors, reason]: Parameters<NonNullable<Reporter["onTestRunEnd"]>>): void {
    const checks: Check[] = [];
    const unreliable = errors.length > 0 || reason === "interrupted";
    for (const module of modules) {
      const file = relative(process.cwd(), module.moduleId).replaceAll("\\", "/");
      for (const test of module.children.allTests()) {
        const tag = parseTestName(test.name);
        if (!tag) continue;
        const state = test.result().state;
        const status: Status = state === "failed" || state === "skipped" ? state
          : state === "passed" && !unreliable && !test.options.fails ? "passed" : "unknown";
        checks.push({
          spec_id: tag.specId,
          kind: tag.kind,
          runner: "vitest",
          name: `${file}::${test.fullName}`,
          status,
        });
      }
    }
    // Workers may complete in any order; keep evidence stable.
    checks.sort((a, b) => a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
    mkdirSync(dirname(this.output), { recursive: true });
    try {
      writeFileSync(this.tmp, JSON.stringify({ schema_version: 1, checks }, null, 2) + "\n", {
        flag: "wx",
      });
      renameSync(this.tmp, this.output);
    } finally {
      rmSync(this.tmp, { force: true });
    }
  }
}
