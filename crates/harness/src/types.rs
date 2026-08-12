//! Lean rung model, deserialized directly from `registry.json` — the
//! canonical MAL-51 ladder. Only the fields the verification harness needs are
//! modeled; any extra fields present in the JSON are ignored by serde.

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
    /// Input is a seed-derived byte string whose LENGTH is also drawn from the
    /// seed, and the output is computed over the whole of it.
    ///
    /// Every other family fixes the output width in the rung definition, so a
    /// program can be written straight-line: read a known number of bytes, emit
    /// a known number back. A stream rung cannot be, because the program does
    /// not know how much input it will get — it has to loop until the input
    /// runs out. That is the one thing thirty-seven rungs never asked for, and
    /// in Malbolge it is the hard part: every cell that executes is enciphered
    /// afterwards, so a loop body is different code on its second pass and must
    /// either restore itself or ride the 94-cycle back.
    Stream,
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
    /// Stream only: output is one byte, the number of input bytes.
    Length,
    /// Stream only: output is one byte, the sum of the input bytes mod 256.
    Checksum,
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
    /// `Stream` only: inclusive bounds on the seed-drawn input length. The
    /// program is told neither the length nor the bounds — it must detect the
    /// end of input itself.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub min_input_len: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_input_len: Option<u32>,
    /// Transform rungs only: sweep the first input byte across all 256 values
    /// instead of sampling it from the seed.
    ///
    /// Sampling cannot separate a near-miss from a solve at the top of the
    /// range. A program correct on 255 of 256 bytes clears eighty sampled draws
    /// about 73% of the time, and this ladder currently sits at 249. Sweeping
    /// makes the judgement deterministic: epoch i fixes case j's first byte to
    /// (i + j) mod 256, so 256 epochs test every byte against every case exactly
    /// once and a single wrong byte is a certain failure.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub exhaustive_first_byte: Option<bool>,
    /// Seed epochs a candidate must pass before the rung counts as solved.
    /// Coverage and finite-map rungs enumerate fixed inputs, so one epoch is
    /// definitive and this stays unset. Transform and hash-prefix rungs redraw
    /// their inputs and targets from the challenge seed every epoch, so a single
    /// epoch can be cleared by a lookup table that got one lucky draw — this is
    /// what stops that being a solve.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub min_epochs: Option<u32>,
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

    /// Seed epochs this rung requires (defaults to 1). `verify` runs at least
    /// this many, so what an agent sees locally is what admission enforces.
    pub fn required_epochs(&self) -> u32 {
        if self.exhaustive_first_byte == Some(true) {
            return 256;
        }
        self.min_epochs.unwrap_or(1)
    }

    /// True when this rung sweeps the first input byte rather than sampling it.
    pub fn sweeps_first_byte(&self) -> bool {
        self.exhaustive_first_byte == Some(true)
    }
}
