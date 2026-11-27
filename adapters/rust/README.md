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

With a supported [Kani installation](https://model-checking.github.io/kani/install-guide.html),
run the separate implementation-proof lane:

```sh
cargo kani --harness queue_001_transition
```

Check that the named harness ran, verification succeeded, and all three
coverage goals are reachable before recording a proof result. The harness has
no deliberate input restrictions beyond the two `u8` types and no loops to
unwind. It invokes the same implementation, not an independently rewritten
model. Neither the proof nor the tests cover queue storage, concurrency or I/O.
