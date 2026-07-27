//! The MAL-51 rung ladder, embedded at compile time from `registry.json`.
//!
//! `registry.json` is dumped verbatim from the source project
//! (`mal51 registry show` for every rung, finer-rung-ladder revision) so the
//! ladder here is byte-for-byte the same set of rungs, families, transforms,
//! finite-map inputs, coverage thresholds, and resource limits.

use crate::types::Rung;

const REGISTRY_JSON: &str = include_str!("../registry.json");

/// Parse the full rung ladder.
pub fn load_registry() -> Vec<Rung> {
    serde_json::from_str(REGISTRY_JSON).expect("embedded registry.json is valid")
}

/// Look up a single rung by id.
pub fn find_rung(id: &str) -> Option<Rung> {
    load_registry().into_iter().find(|r| r.id == id)
}
