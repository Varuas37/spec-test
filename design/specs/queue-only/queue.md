# Bounded queue admission pilot

## Related Issue
- [ISSUE-007: Comparable verification evidence](../../issues/007-evidence-and-native-adapters.md)

- **QUEUE-001** [property]: For integer occupancy and capacity between 0 and 255, an enqueue request increments occupancy by one if occupancy is below capacity, denies it without changing occupancy when full, and refuses an invalid state where occupancy exceeds capacity.

This checks admission arithmetic only. It says nothing about storage, scheduling,
concurrency or I/O. Rust exhausts the input pairs, and TypeScript runs both
generated and exhaustive implementation checks. Any solver result must remain
separate from these tests.

### Combining the receipts

Run the adapter commands from their README files and supply their fresh evidence
from this exact checkout:

```bash
spec-test verify --specs design/specs/queue-only --require-issues --evidence /tmp/rust.json \
  --evidence adapters/typescript/.vitest/spec-evidence.json --evidence-output /tmp/combined.json
```


### Source links

- Rust implementation: [`try_enqueue`](../../../adapters/rust/src/lib.rs).
- Rust proof: [`proofs::queue_001_transition`](../../../adapters/rust/src/lib.rs).

The Rust attributes share the `QUEUE-001` ID with this requirement. Use
`spec-test trace` to locate each attribute at its current line.
