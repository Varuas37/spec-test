# Rust spec-test pilot

The same pure Rust function is exercised by example tests, exhaustive checks
of the finite input domain, and an optional Kani harness. The native adapter
has no dependencies and does not need a procedural macro.

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
exhaustive check, not a solver proof. The Kani row is explicitly `skipped`:
this binary never runs Kani or upgrades that result automatically.

For opt-in implementation-proof evidence, [install and set up Kani 0.68.0](https://model-checking.github.io/kani/install-guide.html)
first. With Python 3.11+ and that Kani installation on `PATH`, run from this
directory:

```sh
cargo run --locked --quiet --bin verify -- --native-only > rust.json
python verify_kani.py > kani.json
```

The producer accepts only a fresh native Kani export from this invocation:
the exact named harness must complete successfully, its implementation checks
must pass, and the invalid, full, and available states must all be reachable.
It exits nonzero and emits a `failed` proof row if the check cannot be
established. The native-only flag omits the ordinary runner's `skipped` Kani
placeholder so both receipts can be passed to `spec-test verify` together.

The harness has no deliberate input restrictions beyond the two `u8` types
and no loops to unwind. It invokes the same implementation, not an
independently rewritten model. Neither the proof nor the tests cover queue
storage, concurrency or I/O.

Run the producer's report and failure tests without installing Kani:

```sh
python -m unittest discover -p 'test_verify_kani.py'
```
