//! Shared grammar for Rust annotations, used by the compiler and the indexer.

use syn::{LitStr, Result, parse::Parse};

/// A single literal requirement ID such as `QUEUE-001`.
pub struct SpecId(pub LitStr);

impl Parse for SpecId {
    fn parse(input: syn::parse::ParseStream<'_>) -> Result<Self> {
        let literal: LitStr = input.parse()?;
        let value = literal.value();
        let valid = value.split_once('-').is_some_and(|(prefix, suffix)| {
            let mut letters = prefix.bytes();
            letters.next().is_some_and(|b| b.is_ascii_uppercase())
                && letters.all(|b| b.is_ascii_uppercase() || b.is_ascii_digit())
                && !suffix.is_empty()
                && suffix.bytes().all(|b| b.is_ascii_digit())
        });
        if !valid {
            return Err(syn::Error::new(
                literal.span(),
                "expected an ASCII requirement ID like QUEUE-001",
            ));
        }
        Ok(Self(literal))
    }
}
