//! Runs the adapter's native evidence lanes and emits a v1 receipt.

use spec_test_rust_queue::{ContractError, EnqueueResult, try_enqueue};
use std::process::ExitCode;

fn queue_examples() -> Result<(), String> {
    let cases = [
        (
            0,
            0,
            Ok(EnqueueResult {
                accepted: false,
                len: 0,
            }),
        ),
        (
            254,
            255,
            Ok(EnqueueResult {
                accepted: true,
                len: 255,
            }),
        ),
        (
            255,
            255,
            Ok(EnqueueResult {
                accepted: false,
                len: 255,
            }),
        ),
        (
            255,
            254,
            Err(ContractError::OccupancyExceedsCapacity {
                len: 255,
                capacity: 254,
            }),
        ),
    ];

    for (len, capacity, expected) in cases {
        let actual = try_enqueue(len, capacity);
        if actual != expected {
            return Err(format!(
                "len={len}, capacity={capacity}: expected {expected:?}, got {actual:?}"
            ));
        }
    }
    Ok(())
}

fn queue_exhaustive() -> Result<(), String> {
    for len in u8::MIN..=u8::MAX {
        for capacity in u8::MIN..=u8::MAX {
            let outcome = try_enqueue(len, capacity);
            let valid = match outcome {
                Ok(result) => {
                    len <= capacity
                        && result.accepted == (len < capacity)
                        && u16::from(result.len) == u16::from(len) + u16::from(result.accepted)
                        && result.len <= capacity
                }
                Err(ContractError::OccupancyExceedsCapacity {
                    len: actual_len,
                    capacity: actual_capacity,
                }) => len > capacity && actual_len == len && actual_capacity == capacity,
            };
            if !valid {
                return Err(format!(
                    "len={len}, capacity={capacity}: contract failed with {outcome:?}"
                ));
            }
        }
    }
    Ok(())
}

fn status(check: fn() -> Result<(), String>) -> &'static str {
    match std::panic::catch_unwind(check) {
        Ok(Ok(())) => "passed",
        Ok(Err(error)) => {
            eprintln!("{error}");
            "failed"
        }
        Err(_) => "failed",
    }
}

fn main() -> ExitCode {
    if std::env::args_os().nth(1).is_some() {
        eprintln!("Usage: verify");
        return ExitCode::from(2);
    }
    let examples = status(queue_examples);
    let exhaustive = status(queue_exhaustive);
    // The native runner only reports the checks it actually executed.
    println!(
        r#"{{"schema_version":1,"checks":[{{"spec_id":"QUEUE-001","kind":"test","runner":"cargo","name":"queue_examples","status":"{examples}"}},{{"spec_id":"QUEUE-001","kind":"property","runner":"cargo","name":"queue_exhaustive","status":"{exhaustive}","details":"Exhaustive 65,536 pairs of u8 inputs; not a solver proof."}}]}}"#
    );
    if examples == "passed" && exhaustive == "passed" {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

#[cfg(test)]
mod tests {
    use super::{queue_examples, queue_exhaustive, status};

    #[test]
    fn examples() {
        queue_examples().unwrap();
    }

    #[test]
    fn entire_u8_input_domain() {
        queue_exhaustive().unwrap();
    }

    #[test]
    fn verification_failure_is_not_reported_as_passed() {
        assert_eq!(status(|| Err("failed contract".into())), "failed");
        assert_eq!(status(|| panic!("panic during check")), "failed");
    }
}
