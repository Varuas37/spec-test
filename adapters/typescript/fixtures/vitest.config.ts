import { defineConfig } from "vitest/config";
import SpecReporter from "../src/reporter.js";

export default defineConfig({
  test: {
    include: ["fixtures/status.fixture.ts"],
    reporters: [new SpecReporter(".vitest/spec-evidence-fixture.json")],
  },
});
