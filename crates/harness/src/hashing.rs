//! Domain-separated SHA-256 hashing, byte-for-byte identical to the source
//! MAL-51 protocol crate. Challenge inputs for the non-finite-map rung
//! families are derived from these hashes, so reproducing them exactly is what
//! lets this standalone harness derive the same cases the source chain does.
//!
//! Canonical encoding: `bincode` with fixint (little-endian) encoding, prefixed
//! by the domain string and a NUL separator.

use bincode::Options;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fmt;

/// A 32-byte SHA-256 digest. Serializes (via bincode fixint) as its raw 32
/// bytes, exactly like the source protocol `Hash32`.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
pub struct Hash32(pub [u8; 32]);

impl Hash32 {
    pub const ZERO: Self = Self([0; 32]);

    pub fn to_hex(self) -> String {
        hex::encode(self.0)
    }
}

impl fmt::Display for Hash32 {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", hex::encode(self.0))
    }
}

/// Canonical `bincode` serialization: fixint (little-endian) encoding.
pub fn canonical_bytes<T: Serialize>(value: &T) -> Vec<u8> {
    bincode::DefaultOptions::new()
        .with_fixint_encoding()
        .serialize(value)
        .expect("canonical serialization is infallible for supported types")
}

fn domain_separated_bytes<T: Serialize>(domain: &str, value: &T) -> Vec<u8> {
    let mut bytes = domain.as_bytes().to_vec();
    bytes.push(0);
    bytes.extend(canonical_bytes(value));
    bytes
}

/// `SHA-256(domain || 0x00 || bytes)`.
pub fn hash_bytes(domain: &str, bytes: &[u8]) -> Hash32 {
    let mut hasher = Sha256::new();
    hasher.update(domain.as_bytes());
    hasher.update([0]);
    hasher.update(bytes);
    Hash32(hasher.finalize().into())
}

/// `hash_bytes(domain, domain || 0x00 || canonical_bytes(value))` — matches the
/// source protocol's `hash_serialized` (the domain string is folded in twice,
/// once by `domain_separated_bytes` and once by `hash_bytes`; preserved here so
/// digests are bit-identical).
pub fn hash_serialized<T: Serialize>(domain: &str, value: &T) -> Hash32 {
    let bytes = domain_separated_bytes(domain, value);
    hash_bytes(domain, &bytes)
}
