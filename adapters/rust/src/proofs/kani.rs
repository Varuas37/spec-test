//! Optional Kani backend for the queue implementation proof.

use super::{ContractError, try_enqueue};

/// QUEUE-001: all u8 pairs, no narrowed assumptions, no loops or I/O.
#[spec_test::verifies("QUEUE-001")]
#[kani::proof]
fn queue_001_transition() {
    let len: u8 = kani::any();
    let capacity: u8 = kani::any();
    let outcome = try_enqueue(len, capacity);

    kani::cover!(len > capacity, "invalid occupancy");
    kani::cover!(len == capacity, "full queue");
    kani::cover!(len < capacity, "available slot");

    if len > capacity {
        assert_eq!(
            outcome,
            Err(ContractError::OccupancyExceedsCapacity { len, capacity })
        );
    } else {
        let result = outcome.expect("valid queue state");
        assert_eq!(result.accepted, len < capacity);
        // Widen before adding so the specification cannot itself overflow.
        assert_eq!(
            u16::from(result.len),
            u16::from(len) + u16::from(result.accepted)
        );
        assert!(result.len <= capacity);
    }
}
