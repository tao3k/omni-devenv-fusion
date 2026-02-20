//! # omni-macros
//!
//! Common procedural macros for omni Rust crates.
//!
//! ## Macros
//!
//! ### Code Generation
//! - [`patterns!`] - Generate pattern constants for symbol extraction
//! - [`topics!`] - Generate topic/event constants
//! - [`py_from!`] - Generate `PyO3` From implementations
//!
//! ### Testing Utilities
//! - [`temp_dir!`] - Create a temporary directory for tests
//! - [`assert_timing!`] - Assert timing constraint for benchmarks
//! - [`bench_case!`] - Create a benchmark test case

use proc_macro::TokenStream;
use quote::quote;
use syn::{Expr, parse_macro_input};

/// Generate pattern constants for symbol extraction.
#[proc_macro]
pub fn patterns(input: TokenStream) -> TokenStream {
    let items = parse_macro_input!(
        input with syn::punctuated::Punctuated::<Expr, syn::Token![,]>::parse_terminated
    );

    let mut expanded = Vec::with_capacity(items.len());
    for expr in items {
        match expr {
            Expr::Tuple(tuple) if tuple.elems.len() == 2 => {
                let name = &tuple.elems[0];
                let pattern = &tuple.elems[1];
                expanded.push(quote! {
                    pub const #name: &str = #pattern;
                });
            }
            Expr::Tuple(tuple) => {
                return syn::Error::new_spanned(
                    tuple,
                    "patterns! requires tuple of (NAME, pattern_string)",
                )
                .to_compile_error()
                .into();
            }
            other => {
                return syn::Error::new_spanned(
                    other,
                    "patterns! requires tuple of (NAME, pattern_string)",
                )
                .to_compile_error()
                .into();
            }
        }
    }

    quote! {
        #(#expanded)*
    }
    .into()
}

/// Generate topic/event constants.
#[proc_macro]
pub fn topics(input: TokenStream) -> TokenStream {
    let items = parse_macro_input!(
        input with syn::punctuated::Punctuated::<Expr, syn::Token![,]>::parse_terminated
    );

    let mut expanded = Vec::with_capacity(items.len());
    for expr in items {
        match expr {
            Expr::Tuple(tuple) if tuple.elems.len() == 2 => {
                let name = &tuple.elems[0];
                let value = &tuple.elems[1];
                expanded.push(quote! {
                    pub const #name: &str = #value;
                });
            }
            Expr::Tuple(tuple) => {
                return syn::Error::new_spanned(
                    tuple,
                    "topics! requires tuple of (CONST_NAME, string_value)",
                )
                .to_compile_error()
                .into();
            }
            other => {
                return syn::Error::new_spanned(
                    other,
                    "topics! requires tuple of (CONST_NAME, string_value)",
                )
                .to_compile_error()
                .into();
            }
        }
    }

    quote! {
        #(#expanded)*
    }
    .into()
}

/// Generate `PyO3` From implementations for wrapper types.
#[proc_macro]
pub fn py_from(input: TokenStream) -> TokenStream {
    let items: Vec<Expr> = parse_macro_input!(
        input with syn::punctuated::Punctuated::<Expr, syn::Token![,]>::parse_terminated
    )
    .into_iter()
    .collect();

    if items.len() != 2 {
        return syn::Error::new(
            proc_macro2::Span::call_site(),
            "py_from! requires exactly 2 arguments: (PyType, InnerType)",
        )
        .to_compile_error()
        .into();
    }

    let py_type = &items[0];
    let inner_type = &items[1];

    quote! {
        impl From<#inner_type> for #py_type {
            fn from(inner: #inner_type) -> Self {
                Self { inner }
            }
        }
    }
    .into()
}

// ============================================================================
// Testing Utilities
// ============================================================================

/// Create a temporary directory for tests.
///
/// # Example
///
/// ```rust
/// let temp_path = omni_macros::temp_dir!();
/// std::fs::write(temp_path.join("test.txt"), "hello")
///     .expect("temporary write should succeed");
/// assert!(temp_path.exists());
/// ```
#[proc_macro]
pub fn temp_dir(_input: TokenStream) -> TokenStream {
    quote! {
        {
            let path = std::env::temp_dir()
                .join(format!("omni_test_{}", uuid::Uuid::new_v4()));
            std::fs::create_dir_all(&path)
                .expect("Failed to create temp directory");
            path
        }
    }
    .into()
}

/// Assert timing constraint for benchmarks.
///
/// # Example
///
/// ```rust
/// let _elapsed = omni_macros::assert_timing!(100.0, {
///     std::thread::sleep(std::time::Duration::from_millis(1));
/// });
/// ```
#[proc_macro]
pub fn assert_timing(input: TokenStream) -> TokenStream {
    let items: Vec<Expr> = parse_macro_input!(
        input with syn::punctuated::Punctuated::<Expr, syn::Token![,]>::parse_terminated
    )
    .into_iter()
    .collect();

    if items.len() != 2 {
        return syn::Error::new(
            proc_macro2::Span::call_site(),
            "assert_timing! requires 2 arguments: (max_ms, block)",
        )
        .to_compile_error()
        .into();
    }

    let max_ms = &items[0];
    let block = &items[1];

    quote! {
        {
            let start = std::time::Instant::now();
            #block
            let elapsed = start.elapsed();
            let ms = elapsed.as_secs_f64() * 1000.0;
            assert!(
                ms < #max_ms,
                "Operation took {:.2}ms, expected < {}ms",
                ms,
                #max_ms
            );
            elapsed
        }
    }
    .into()
}

/// Create a benchmark test case with timing.
///
/// # Example
///
/// ```rust
/// let elapsed = omni_macros::bench_case!(|| {
///     let value = 1 + 1;
///     assert_eq!(value, 2);
/// });
/// let _ = elapsed;
/// ```
#[proc_macro]
pub fn bench_case(input: TokenStream) -> TokenStream {
    let block = parse_macro_input!(input as syn::Expr);

    quote! {
        {
            let start = std::time::Instant::now();
            let _ = #block;
            start.elapsed()
        }
    }
    .into()
}
