//! The MAL-51 rung ladder, embedded at compile time from `registry.json`.
//!
//! Published rung definitions are frozen: families, transforms, inputs,
//! thresholds, and resource limits never change once a rung is on the board.
//! Additions (map7a/map7b, the cov36–cov48 steps) are strictly additive and
//! say so in their `purpose` fields.

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
