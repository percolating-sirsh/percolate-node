//! Storage iterators.

/// Iterator over keys with prefix.
pub struct PrefixIterator<'a> {
    iter: rocksdb::DBRawIterator<'a>,
    prefix: Vec<u8>,
}

impl<'a> PrefixIterator<'a> {
    /// Create new prefix iterator.
    pub fn new(mut iter: rocksdb::DBRawIterator<'a>, prefix: Vec<u8>) -> Self {
        iter.seek(&prefix);
        Self { iter, prefix }
    }
}

impl<'a> Iterator for PrefixIterator<'a> {
    type Item = (Vec<u8>, Vec<u8>);

    fn next(&mut self) -> Option<Self::Item> {
        if !self.iter.valid() {
            return None;
        }

        let key = self.iter.key()?;

        // Check if key still has prefix
        if !key.starts_with(&self.prefix) {
            return None;
        }

        let value = self.iter.value()?.to_vec();
        let key = key.to_vec();

        self.iter.next();

        Some((key, value))
    }
}
