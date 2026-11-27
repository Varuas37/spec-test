import { defineConfig } from "vitest/config";
import SpecReporter from "./src/reporter.js";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    reporters: ["default", new SpecReporter()],
  },
});
