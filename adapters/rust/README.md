# Rust spec-test pilot

The same pure Rust function is exercised by example tests, exhaustive checks
of the finite input domain, and an optional Kani harness. The native adapter
uses a small compile-time attribute crate; the annotations add no runtime behavior.

**QUEUE-001:** Given a queue length and capacity from 0 to 255, requesting one
slot increases the length by one and reports acceptance when there is room.
A full queue does not change. An invalid state (length greater than capacity)
returns a typed contract error, including on release builds.

From this directory:

```sh
cargo test --locked
cargo run --locked --quiet --bin verify
```

The second command emits one schema-version-1 receipt on stdout. It checks the
real `try_enqueue` implementation on all 65,536 input pairs; a failing check
reports `failed` and the process exits nonzero. The property result is a finite
exhaustive check, not a solver proof. The native runner emits only the
checks it actually ran and knows nothing about proof engines.

For opt-in implementation-proof evidence, [install and set up Kani 0.68.0](https://model-checking.github.io/kani/install-guide.html)
first. With Python 3.11+ and that Kani installation on `PATH`, run from this
directory:

```sh
cargo run --locked --quiet --bin verify > rust.json
python verify_kani.py > kani.json
```

The producer accepts only a fresh native Kani export from this invocation:
the exact named harness must complete successfully, its implementation checks
must pass, and the invalid, full, and available states must all be reachable.
It exits nonzero and emits a `failed` proof row if the check cannot be
established. The harness lives in `src/proofs/kani.rs`, conditionally loaded
only in Kani builds. Ordinary builds and the trace scanner do not require
a Kani installation.

### Use a different proof engine

Keep the Rust implementation, spec ID and attribute vocabulary. Write the
new engine's harness and a separate adapter that emits a standard version-1
evidence receipt. Pass that receipt with `spec-test verify --evidence`; the
consumer is shared and does not invoke or require Kani. Use the adapter's own
`runner` name and classify the result as `implementation-proof` only when it
checks the actual implementation. A model of the same rule is `model-proof`;
an exhaustive finite test is `property`. Emit failed, unknown or no receipt
when an implementation proof cannot be established. Only import receipts from
trusted runners, since a receipt is not an attestation.

The harness has no deliberate input restrictions beyond the two `u8` types
and no loops to unwind. It invokes the same implementation, not an
independently rewritten model. Neither the proof nor the tests cover queue
storage, concurrency or I/O.

Run the producer's report and failure tests without installing Kani:

```sh
python -m unittest discover -p 'test_verify_kani.py'
```


## Trace a requirement to Rust and its Kani harness

Add `#[spec_test::implements("QUEUE-001")]` to the function and
`#[spec_test::verifies("QUEUE-001")]` to its test or proof. Keep
`#[kani::proof]` on the harness; only Kani runs it. The dependency key
`spec_test` in the adapter's Cargo manifest aliases the local macro package.
Use these canonical paths on module-level functions so the scanner can find
them. Scanning follows the source syntax, not the active build configuration;
pass any external module files you want indexed explicitly.

From the repository root:

```sh
cargo run --locked --quiet --manifest-path adapters/rust/Cargo.toml \
  -p spec-test-rust-trace -- adapters/rust/src/lib.rs adapters/rust/src/proofs/kani.rs > /tmp/rust-trace.json
spec-test trace --specs design/specs/queue-only --index /tmp/rust-trace.json \
  --require QUEUE-001
```

The version-1 source index uses `spec_id`, `role` (`implements` or
`verifies`), `language`, repository-relative `file`, 1-based `line` and
lexical `symbol`. Future language scanners can emit the same format.
The Markdown declaration owns the requirement wording. CI checks the presence
of both roles and rejects unknown IDs and duplicate links. The index is a
navigation aid, not a result: a label does not prove that a harness ran or
passed. For that use separately produced evidence with `spec-test verify`.
