//! The MAL-51 rung ladder, embedded at compile time from `registry.json`.
//!
//! Presentation is maintained separately in `leaderboard/ladder.json`.
//! Prefer additive successor IDs for changed task limits or distributions;
//! explicit contract repairs require digest tracking and re-verification.

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
