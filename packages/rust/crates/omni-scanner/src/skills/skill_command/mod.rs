//! Skill Command module for @skill_command decorator parsing.
//!
//! Provides modular parsing of @skill_command decorators:
//! - [`category`] - Category inference from skill names
//! - [`parser`] - Decorator and function parsing utilities
//! - [`annotations`] - Tool annotation heuristics

pub mod annotations;
pub mod category;
pub mod parser;
