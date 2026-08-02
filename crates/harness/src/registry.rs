//! The MAL-51 rung ladder, embedded at compile time from `registry.json`.
//!
//! The original 29 rungs in `registry.json` are dumped verbatim from the
//! source project (`mal51 registry show` for every rung, finer-rung-ladder
//! revision). Difficulty-smoothing rungs added since (map7a/map7b, the
//! cov36–cov48 steps) are minted in this repo, marked in their `purpose`
//! fields, and strictly additive: a published rung id never changes meaning.

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
