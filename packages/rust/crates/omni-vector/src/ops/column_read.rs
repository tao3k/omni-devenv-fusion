//! Read string values from columns that may be Utf8 or Dictionary<Int32, Utf8>.
//! List columns (routing_keywords, intents) support List<Utf8> and legacy Utf8 (split by separator).

use lance::deps::arrow_array::Array;
use lance::deps::arrow_array::StringArray;
use lance::deps::arrow_array::array::ArrayAccessor;
use lance::deps::arrow_array::types::Int32Type;
use lance::deps::arrow_array::{DictionaryArray, ListArray};

/// Returns the string at row index `i` for a column that may be Utf8 or Dictionary<Int32, Utf8>.
/// Returns empty string when the column is null at `i` or the column type is unsupported.
#[inline]
pub fn get_utf8_at(array: &dyn Array, i: usize) -> String {
    if let Some(s) = array.as_any().downcast_ref::<StringArray>() {
        if s.is_null(i) {
            return String::new();
        }
        return s.value(i).to_string();
    }
    if let Some(d) = array.as_any().downcast_ref::<DictionaryArray<Int32Type>>() {
        if let Some(typed) = d.downcast_dict::<StringArray>() {
            if typed.is_null(i) {
                return String::new();
            }
            return typed.value(i).to_string();
        }
    }
    String::new()
}

/// Returns the list of strings at row index `i` for a column that may be List<Utf8> or legacy Utf8.
/// For ListArray: returns the element strings. For Utf8 (legacy): splits by the given separator.
#[inline]
fn get_string_list_at_impl(
    array: &dyn Array,
    i: usize,
    legacy_split: fn(&str) -> Vec<String>,
) -> Vec<String> {
    if let Some(list) = array.as_any().downcast_ref::<ListArray>() {
        if list.is_null(i) {
            return Vec::new();
        }
        let slice = list.value(i);
        let str_arr = match slice.as_any().downcast_ref::<StringArray>() {
            Some(a) => a,
            None => return Vec::new(),
        };
        return (0..str_arr.len())
            .map(|j| {
                if str_arr.is_null(j) {
                    String::new()
                } else {
                    str_arr.value(j).to_string()
                }
            })
            .collect();
    }
    if let Some(s) = array.as_any().downcast_ref::<StringArray>() {
        if s.is_null(i) {
            return Vec::new();
        }
        return legacy_split(s.value(i));
    }
    Vec::new()
}

/// Routing keywords at row `i`. Supports List<Utf8> (v3) and legacy Utf8 (space-separated).
#[inline]
pub fn get_routing_keywords_at(array: &dyn Array, i: usize) -> Vec<String> {
    get_string_list_at_impl(array, i, |s| {
        s.split_whitespace().map(String::from).collect()
    })
}

/// Intents at row `i`. Supports List<Utf8> (v3) and legacy Utf8 (pipe-separated).
#[inline]
pub fn get_intents_at(array: &dyn Array, i: usize) -> Vec<String> {
    get_string_list_at_impl(array, i, |s| {
        s.split('|')
            .map(|x| x.trim().to_string())
            .filter(|x| !x.is_empty())
            .collect()
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use lance::deps::arrow_array::types::Int32Type;
    use lance::deps::arrow_array::{DictionaryArray, Int32Array, StringArray};
    use std::sync::Arc;

    #[test]
    fn get_utf8_at_string_array() {
        let arr = StringArray::from(vec!["a", "bb", "ccc"]);
        assert_eq!(get_utf8_at(&arr, 0), "a");
        assert_eq!(get_utf8_at(&arr, 1), "bb");
        assert_eq!(get_utf8_at(&arr, 2), "ccc");
    }

    #[test]
    fn get_utf8_at_string_array_null() {
        let arr = StringArray::from(vec![Some("x"), None, Some("z")]);
        assert_eq!(get_utf8_at(&arr, 0), "x");
        assert_eq!(get_utf8_at(&arr, 1), "");
        assert_eq!(get_utf8_at(&arr, 2), "z");
    }

    #[test]
    fn get_utf8_at_dictionary_array() {
        let values = StringArray::from(vec!["git", "writer", "knowledge"]);
        let keys = Int32Array::from(vec![0, 1, 0, 2]); // git, writer, git, knowledge
        let dict = DictionaryArray::<Int32Type>::try_new(keys, Arc::new(values)).unwrap();
        assert_eq!(get_utf8_at(&dict, 0), "git");
        assert_eq!(get_utf8_at(&dict, 1), "writer");
        assert_eq!(get_utf8_at(&dict, 2), "git");
        assert_eq!(get_utf8_at(&dict, 3), "knowledge");
    }

    #[test]
    fn get_utf8_at_dictionary_low_cardinality() {
        let values = StringArray::from(vec!["cat_a", "cat_b"]);
        let keys = Int32Array::from(vec![0, 0, 1, 0]);
        let dict = DictionaryArray::<Int32Type>::try_new(keys, Arc::new(values)).unwrap();
        assert_eq!(get_utf8_at(&dict, 0), "cat_a");
        assert_eq!(get_utf8_at(&dict, 2), "cat_b");
    }
}
