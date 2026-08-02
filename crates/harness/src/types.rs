//! Lean rung model. Deserialized directly from `registry.json`, which is
//! sourced from the MAL-51 registry so the rung ladder here is
//! ground-truth-identical to the source project. Only the fields the
//! verification harness needs are modeled; any extra fields present in the JSON
//! are ignored by serde.

use serde::{Deserialize, Serialize};

/// The five challenge families. Each derives its per-case inputs and expected
/// outputs differently (see `challenge.rs`).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize, Serialize)]
pub enum Family {
    /// Output = first `output_bytes` of the (hash-derived) input.
    EchoPrefix,
    /// Output = SHA-256(seed, input, index) truncated to `output_bytes`.
    HashPrefix,
    /// Output = `transform(prefix)`, input hash-derived per case.
    Transform,
    /// Output = `transform(byte)` over a fixed list of input bytes.
    FiniteMap,
    /// Like `Transform` but cases enumerate all 256 input bytes; a rung passes
    /// when at least `min_correct_cases` cases are correct.
    CoverageTransform,
}

/// Per-byte transforms applied by the `Transform` / `FiniteMap` /
/// `CoverageTransform` families.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize, Serialize)]
pub enum Transform {
    Identity,
    Reverse,
    XorMask,
    /// `crazy(byte, 0x51) % 256` using the classic-Malbolge crazy operation.
    CrazyMask,
    RotateLeft,
    NibbleMap,
}

/// One rung of the MAL-51 ladder. Serializes to the same JSON shape it
/// deserializes from, so a generated rung file is directly loadable by
/// `verify --rung-file`.
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Rung {
    pub id: String,
    pub title: String,
    pub level: u32,
    pub status: String,
    pub family: Family,
    pub transform: Transform,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub finite_map_inputs: Vec<u8>,
    pub output_bytes: u32,
    pub cases: u32,
    /// Only present for `CoverageTransform` rungs.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub min_correct_cases: Option<u32>,
    pub max_program_len: u64,
    pub max_steps_per_case: u64,
    pub max_output_len: u64,
    pub max_memory_cells: u64,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub purpose: String,
}

/// A single derived challenge case: one input and its expected output.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ChallengeCase {
    pub index: u32,
    pub input: Vec<u8>,
    pub expected_output: Vec<u8>,
}

impl Rung {
    pub fn is_coverage(&self) -> bool {
        self.family == Family::CoverageTransform
    }

    /// Threshold of correct cases required to pass a coverage rung (defaults to
    /// all cases when unset). Meaningless for non-coverage rungs.
    pub fn required_correct(&self) -> u32 {
        self.min_correct_cases.unwrap_or(self.cases)
    }
}
