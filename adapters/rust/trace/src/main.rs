//! Extract source locations from real Rust syntax without executing the crate.

use serde_json::{Value, json};
use spec_test_rust_syntax::SpecId;
use std::{collections::BTreeSet, env, error::Error, fs, path::Path};
use syn::{Attribute, ItemFn, ItemMod, spanned::Spanned, visit::Visit};

fn role(attr: &Attribute) -> Option<&'static str> {
    let mut segments = attr.path().segments.iter();
    if segments.next()?.ident != "spec_test" {
        return None;
    }
    let candidate = segments.next()?;
    if segments.next().is_some() {
        return None;
    }
    match candidate.ident.to_string().as_str() {
        "implements" => Some("implements"),
        "verifies" => Some("verifies"),
        _ => None,
    }
}

#[derive(Default)]
struct Scanner {
    modules: Vec<String>,
    rows: Vec<Value>,
    errors: Vec<String>,
    in_block: bool,
}

impl<'ast> Visit<'ast> for Scanner {
    fn visit_item_mod(&mut self, module: &'ast ItemMod) {
        self.modules.push(module.ident.to_string());
        syn::visit::visit_item_mod(self, module);
        self.modules.pop();
    }

    fn visit_item_fn(&mut self, function: &'ast ItemFn) {
        let mut chain = self.modules.clone();
        chain.push(function.sig.ident.to_string());
        let symbol = chain.join("::");
        let mut seen = BTreeSet::new();
        for attr in &function.attrs {
            let Some(role) = role(attr) else { continue };
            if self.in_block {
                self.visit_attribute(attr);
                continue;
            }
            let line = attr.span().start().line;
            match attr.parse_args::<SpecId>() {
                Ok(id) => {
                    let id = id.0.value();
                    if !seen.insert((role, id.clone())) {
                        self.errors
                            .push(format!("line {line}: duplicate {role} on {symbol}"));
                    }
                    self.rows.push(json!({
                        "spec_id": id, "role": role, "symbol": symbol, "line": line,
                    }));
                }
                Err(error) => self.errors.push(format!("line {line}: {error}")),
            }
        }
        self.visit_block(&function.block);
    }

    fn visit_block(&mut self, block: &'ast syn::Block) {
        let was_in_block = std::mem::replace(&mut self.in_block, true);
        syn::visit::visit_block(self, block);
        self.in_block = was_in_block;
    }

    fn visit_attribute(&mut self, attr: &'ast Attribute) {
        if role(attr).is_some() {
            self.errors.push(format!(
                "line {}: requirement attributes must label module-level functions",
                attr.span().start().line
            ));
        }
    }
}

fn scan(path: &str, source: &str) -> Result<Vec<Value>, Box<dyn Error>> {
    let mut scanner = Scanner::default();
    scanner.visit_file(&syn::parse_file(source)?);
    if !scanner.errors.is_empty() {
        return Err(format!("{path}: {}", scanner.errors.join("; ")).into());
    }
    for row in &mut scanner.rows {
        row["file"] = json!(path);
        row["language"] = json!("rust");
    }
    Ok(scanner.rows)
}

fn run() -> Result<(), Box<dyn Error>> {
    let root = env::current_dir()?.canonicalize()?;
    let files: BTreeSet<_> = env::args_os()
        .skip(1)
        .map(fs::canonicalize)
        .collect::<Result<_, _>>()?;
    if files.is_empty() {
        return Err(
            "usage: spec-test-rust-trace PATH.rs [PATH.rs ...] from the project root".into(),
        );
    }
    let mut rows = Vec::new();
    for file in files {
        let relative = file.strip_prefix(&root)?;
        if relative.extension() != Some("rs".as_ref()) || !file.is_file() {
            return Err(format!("expected Rust source file: {}", file.display()).into());
        }
        let path = portable_path(relative).ok_or("source path must be UTF-8")?;
        let text = fs::read_to_string(file)?;
        rows.extend(scan(&path, &text)?);
    }
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"schema_version": 1, "links": rows}))?
    );
    Ok(())
}

fn portable_path(path: &Path) -> Option<String> {
    path.iter()
        .map(|part| part.to_str())
        .collect::<Option<Vec<_>>>()
        .map(|parts| parts.join("/"))
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_multiline_attributes_and_nested_modules_not_strings_or_comments() {
        let rows = scan(
            "src/lib.rs",
            r##"
            // #[spec_test::implements("FAKE-001")]
            const TEXT: &str = "#[spec_test::verifies(\"FAKE-002\")]";
            mod proof {
                #[spec_test::verifies(
                    "QUEUE-001"
                )]
                fn queue_proof() {}
            }
        "##,
        )
        .unwrap();
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0]["symbol"], "proof::queue_proof");
        assert_eq!(rows[0]["line"], 5);
        assert_eq!(rows[0]["spec_id"], "QUEUE-001");
    }

    #[test]
    fn refuses_invalid_duplicate_and_misplaced_attributes() {
        for source in [
            "#[spec_test::implements(\"bad\")] fn f() {}",
            "#[spec_test::implements(\"A-1\")] #[spec_test::implements(\"A-1\")] fn f() {}",
            "#[spec_test::verifies(\"A-1\")] struct S;",
            "fn f() { #[spec_test::verifies(\"A-1\")] fn nested() {} }",
            "struct S; impl S { #[spec_test::verifies(\"A-1\")] fn method() {} }",
            r#"struct S; impl S { fn method() { #[spec_test::verifies("A-1")] fn local() {} } }"#,
            r#"trait T { fn method() { #[spec_test::verifies("A-1")] fn local() {} } }"#,
            r#"const X: () = { #[spec_test::verifies("A-1")] fn local() {} };"#,
        ] {
            assert!(scan("src/lib.rs", source).is_err(), "{source}");
        }
    }
}
