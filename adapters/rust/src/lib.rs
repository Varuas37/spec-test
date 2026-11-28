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
#[path = "proofs/kani.rs"]
mod proofs;
