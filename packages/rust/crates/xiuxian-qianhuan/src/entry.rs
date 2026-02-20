/// One Q&A record in the injection window.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct QaEntry {
    /// Question text inserted into `<q>`.
    pub question: String,
    /// Answer text inserted into `<a>`.
    pub answer: String,
    /// Optional source hint inserted into `<source>`.
    pub source: Option<String>,
}

impl QaEntry {
    pub(crate) fn char_len(&self) -> usize {
        self.question.chars().count()
            + self.answer.chars().count()
            + self
                .source
                .as_deref()
                .map_or(0, |value| value.chars().count())
    }
}
