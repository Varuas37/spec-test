//! Compile-time requirement labels. These do not execute tests or prove claims.
//!
//! ```compile_fail
//! #[spec_test_macros::implements("queue-001")]
//! fn invalid_id() {}
//! ```
//!
//! ```compile_fail
//! #[spec_test_macros::verifies("QUEUE-001", "QUEUE-002")]
//! fn multiple_arguments() {}
//! ```
//!
//! ```compile_fail
//! #[spec_test_macros::implements("QUEUE-001")]
//! struct NotAFunction;
//! ```

use proc_macro::TokenStream;
use spec_test_rust_syntax::SpecId;

fn annotate(args: TokenStream, item: TokenStream) -> TokenStream {
    if let Err(error) =
        syn::parse::<SpecId>(args).and_then(|_| syn::parse::<syn::ItemFn>(item.clone()))
    {
        return error.into_compile_error().into();
    }
    item
}

/// Label the function which implements a requirement.
#[proc_macro_attribute]
pub fn implements(args: TokenStream, item: TokenStream) -> TokenStream {
    annotate(args, item)
}

/// Label a test or proof harness for a requirement.
#[proc_macro_attribute]
pub fn verifies(args: TokenStream, item: TokenStream) -> TokenStream {
    annotate(args, item)
}
