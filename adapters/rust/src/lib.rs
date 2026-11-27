//! A finite enqueue transition used by the native tests and the Kani harness.

/// Whether an item was admitted, and how many slots are now occupied.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct EnqueueResult {
    pub accepted: bool,
    pub len: u8,
}

/// The caller supplied a state whose occupancy already exceeds capacity.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ContractError {
    OccupancyExceedsCapacity { len: u8, capacity: u8 },
}

/// Reserve a single item slot without exceeding the queue capacity.
/// A full queue (including capacity zero) does not change state.
#[spec_test::implements("QUEUE-001")]
pub fn try_enqueue(len: u8, capacity: u8) -> Result<EnqueueResult, ContractError> {
    match len.cmp(&capacity) {
        core::cmp::Ordering::Greater => {
            Err(ContractError::OccupancyExceedsCapacity { len, capacity })
        }
        core::cmp::Ordering::Equal => Ok(EnqueueResult {
            accepted: false,
            len,
        }),
        core::cmp::Ordering::Less => Ok(EnqueueResult {
            accepted: true,
            len: len + 1,
        }),
    }
}

#[cfg(kani)]
mod proofs {
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
}
