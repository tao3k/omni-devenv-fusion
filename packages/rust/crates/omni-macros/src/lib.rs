//! # omni-macros
//!
//! Common procedural macros for omni Rust crates.
//!
//! ## Macros
//!
//! ### Code Generation
//! - [`patterns!`] - Generate pattern constants for symbol extraction
//! - [`topics!`] - Generate topic/event constants
//! - [`py_from!`] - Generate PyO3 From implementations
//!
//! ### Testing Utilities
//! - [`temp_dir!`] - Create a temporary directory for tests
//! - [`assert_timing!`] - Assert timing constraint for benchmarks
//! - [`bench_case!`] - Create a benchmark test case

use proc_macro::TokenStream;
use quote::quote;
use syn::{Expr, parse::Parser};

/// Generate pattern constants for symbol extraction.
#[proc_macro]
pub fn patterns(input: TokenStream) -> TokenStream {
    let items: syn::punctuated::Punctuated<Expr, syn::Token![,]> =
        syn::punctuated::Punctuated::parse_terminated
            .parse(input)
            .expect("Failed to parse patterns");

    let expanded = items.into_iter().map(|expr| {
        if let Expr::Tuple(tuple) = expr {
            let elems = tuple.elems;
            if elems.len() != 2 {
                panic!("patterns! requires tuple of (NAME, pattern_string)");
            }
            let name = &elems[0];
            let pattern = &elems[1];
            quote! {
                pub const #name: &str = #pattern;
            }
        } else {
            panic!("patterns! requires tuple of (NAME, pattern_string)");
        }
    });

    quote! {
        #(#expanded)*
    }
    .into()
}

/// Generate topic/event constants.
#[proc_macro]
pub fn topics(input: TokenStream) -> TokenStream {
    let items: syn::punctuated::Punctuated<Expr, syn::Token![,]> =
        syn::punctuated::Punctuated::parse_terminated
            .parse(input)
            .expect("Failed to parse topics");

    let expanded = items.into_iter().map(|expr| {
        if let Expr::Tuple(tuple) = expr {
            let elems = tuple.elems;
            if elems.len() != 2 {
                panic!("topics! requires tuple of (CONST_NAME, string_value)");
            }
            let name = &elems[0];
            let value = &elems[1];
            quote! {
                pub const #name: &str = #value;
            }
        } else {
            panic!("topics! requires tuple of (CONST_NAME, string_value)");
        }
    });

    quote! {
        #(#expanded)*
    }
    .into()
}

/// Generate PyO3 From implementations for wrapper types.
#[proc_macro]
pub fn py_from(input: TokenStream) -> TokenStream {
    let items: syn::punctuated::Punctuated<Expr, syn::Token![,]> =
        syn::punctuated::Punctuated::parse_terminated
            .parse(input)
            .expect("Failed to parse py_from");

    if items.len() != 2 {
        panic!("py_from! requires exactly 2 arguments: (PyType, InnerType)");
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
/// #[test]
/// fn test_with_temp_dir() {
///     let temp_path = temp_dir!();
///     std::fs::write(temp_path.join("test.txt"), "hello").unwrap();
///     assert!(temp_path.exists());
/// }
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
/// #[test]
/// fn test_performance() {
///     assert_timing!(100, {
///         // Code to benchmark
///         std::thread::sleep(std::time::Duration::from_millis(1));
///     });
/// }
/// ```
#[proc_macro]
pub fn assert_timing(input: TokenStream) -> TokenStream {
    let items: syn::punctuated::Punctuated<Expr, syn::Token![,]> =
        syn::punctuated::Punctuated::parse_terminated
            .parse(input)
            .expect("Failed to parse assert_timing");

    if items.len() != 2 {
        panic!("assert_timing! requires 2 arguments: (max_ms, block)");
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
/// #[test]
/// fn bench_my_function() {
///     let elapsed = bench_case!(|| {
///         my_function();
///     });
///     println!("Function took {:?}", elapsed);
/// }
/// ```
#[proc_macro]
pub fn bench_case(input: TokenStream) -> TokenStream {
    let block: syn::Expr = syn::parse(input).expect("Failed to parse bench_case");

    quote! {
        {
            let start = std::time::Instant::now();
            let _ = #block;
            start.elapsed()
        }
    }
    .into()
}
