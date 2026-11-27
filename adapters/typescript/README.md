# TypeScript adapter pilot

From this directory, with Node 22.12+:

```sh
npm ci
npm run verify
cat .vitest/spec-evidence.json
```

The adapter records **executed** Vitest outcomes, not declarations in source.
Use `specTest(id, title, body)` for an ordinary check and
`specProperty(id, title, body)` with `fast-check` for sampled properties.
The ID and kind are part of the test name, so they survive disabled tests and
setup failures. For a deliberately skipped requirement, use
`test.skip(testName(id, "test", title), body)`.
An unrun, untagged, or missing test produces no passing evidence. An expected
failure (`test.fails`) is not passing evidence either. The caller
should require the expected spec IDs, kinds and runners; an empty report never
means the requirements passed. Run verification from CI and require its exit
code as well as the evidence. Do not use filtered runs as full requirement
coverage. Do not run multiple jobs against the same output path.

`contract()` is a synchronous pre/postcondition wrapper for immutable arguments.
The bounded admission example executes real TypeScript/JavaScript code and uses
example tests, 512 generated cases, and a separate exhaustive check of all
65,536 input pairs in the finite u8 domain. Neither is evidence for inputs
outside that domain or for queue storage and concurrency.
Specs, test vectors, and evidence can be shared across languages; solver
outputs belong in a separate model- or implementation-proof lane. This
adapter does not claim to prove general TypeScript or any production runtime.

## Trace implementation and verification locations

Add `/** @specTestImplements QUEUE-001 */` on a named function, a single named
variable declaration, a class, or a class method. Repeat the tag once per
requirement. A class link does not automatically tag its methods. The scanner
also recognizes top-level literal calls to this adapter's imported
`specTest` and `specProperty` helpers. A separate labeled function may use
`@specTestVerifies`; that is a source link, not an executed test.

From the repository root:

```sh
node adapters/typescript/trace.mjs adapters/typescript/src/queue.ts \
  adapters/typescript/test/queue.test.ts > /tmp/ts-trace.json
spec-test trace --specs design/specs/queue-only --index /tmp/ts-trace.json \
  --require QUEUE-001
```

The ts index uses the same schema as Rust; repeat `--index` to combine
languages. Every represented language must provide both roles on its own.
TypeScript Vitest results are separate evidence; this trace is not a solver
proof.
