import { test } from "vitest";

export type TestKind = "test" | "property";

const ID = /^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+$/;

export function testName(specId: string, kind: TestKind, title: string): string {
  if (!ID.test(specId) || !title.trim() || /[\r\n]/.test(title)) {
    throw new TypeError("Specify a requirement ID and a nonempty single-line test title");
  }
  return `[${specId}|${kind}] ${title}`;
}

export function parseTestName(name: string): { specId: string; kind: TestKind } | undefined {
  const match = /^\[([^|\]]+)\|(test|property)\] .+$/u.exec(name);
  if (!match || !ID.test(match[1])) return undefined;
  return { specId: match[1], kind: match[2] === "test" ? "test" : "property" };
}

export function specTest(specId: string, title: string, run: () => void | Promise<void>): void {
  test(testName(specId, "test", title), run);
}

export function specProperty(specId: string, title: string, run: () => void | Promise<void>): void {
  test(testName(specId, "property", title), run);
}
