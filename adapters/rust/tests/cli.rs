use std::process::Command;

#[test]
fn emits_only_executed_native_checks() {
    let output = Command::new(env!("CARGO_BIN_EXE_verify"))
        .output()
        .expect("launch the native receipt runner");
    assert!(output.status.success());
    let receipt = String::from_utf8(output.stdout).unwrap();
    assert_eq!(receipt.lines().count(), 1);
    assert!(receipt.starts_with(r#"{"schema_version":1,"checks":["#));
    assert!(
        receipt.contains(
            r#""kind":"test","runner":"cargo","name":"queue_examples","status":"passed""#
        )
    );
    assert!(receipt.contains(
        r#""kind":"property","runner":"cargo","name":"queue_exhaustive","status":"passed""#
    ));
    assert!(!receipt.contains("implementation-proof"));
    assert!(!receipt.contains("kani"));
}
