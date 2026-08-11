//! Procedural rung generation.
//!
//! `generate-rung` mints unlimited training instances in the two
//! seed-independent families:
//!
//! * **FiniteMap** — k distinct input bytes drawn deterministically from a
//!   generator seed, restricted to a byte-range class (low bytes are
//!   structurally harder for crz-dispatch than high bytes). Each instance is
//!   scored with the dispatch-feasibility estimator so its difficulty class
//!   is honest, not guessed.
//! * **CoverageTransform** — all 256 single-byte inputs with a pass threshold,
//!   the graded-reward variant of an all-or-nothing transform rung.
//!
//! The output is a single JSON object in exactly the registry rung schema
//! (loadable by `verify --rung-file`), plus two advisory blocks — `generator`
//! (full provenance: parameters, seed, schema version) and, for finite maps,
//! `dispatch_feasibility` — which `verify` ignores.
//!
//! Determinism contract: the same parameters and seed always produce the same
//! instance, and expected outputs depend only on the rung definition (both
//! families derive cases independently of the challenge seed). The 29 registry
//! rungs are the fixed public reference ladder; generated instances are the
//! unbounded training supply.

use serde::Serialize;

use crate::dispatch::{feasibility, FeasibilityReport};
use crate::hashing::hash_serialized;
use crate::types::{Family, Rung, Transform};

pub const GENERATOR_SCHEMA: &str = "malbolge-rungs.generate-rung.v1";

/// Byte-range class for finite-map input selection.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, clap::ValueEnum)]
#[serde(rename_all = "lowercase")]
pub enum RangeClass {
    /// 0x00..=0x3f — structurally hardest for crz-dispatch separation.
    Low,
    /// 0x80..=0xff — widest dispatch J-bands, easiest separation.
    High,
    /// 0x00..=0xff — unrestricted.
    Mixed,
}

impl RangeClass {
    fn name(self) -> &'static str {
        match self {
            RangeClass::Low => "low",
            RangeClass::High => "high",
            RangeClass::Mixed => "mixed",
        }
    }

    fn apply(self, byte: u8) -> u8 {
        match self {
            RangeClass::Low => byte & 0x3f,
            RangeClass::High => 0x80 | byte,
            RangeClass::Mixed => byte,
        }
    }

    fn domain_size(self) -> usize {
        match self {
            RangeClass::Low => 64,
            RangeClass::High => 128,
            RangeClass::Mixed => 256,
        }
    }
}

/// CLI-facing transform choice (maps onto `types::Transform`).
#[derive(Clone, Copy, Debug, PartialEq, Eq, clap::ValueEnum)]
pub enum TransformArg {
    /// byte XOR 0x51
    #[value(name = "xor51")]
    Xor51,
    /// crazy(byte, 0x51) mod 256
    #[value(name = "crazy")]
    CrazyMask,
    /// rotate left by one bit
    #[value(name = "rotl")]
    RotateLeft,
    /// swap nibbles
    #[value(name = "nib")]
    NibbleMap,
    /// identity
    #[value(name = "id")]
    Identity,
}

impl TransformArg {
    pub fn to_transform(self) -> Transform {
        match self {
            TransformArg::Xor51 => Transform::XorMask,
            TransformArg::CrazyMask => Transform::CrazyMask,
            TransformArg::RotateLeft => Transform::RotateLeft,
            TransformArg::NibbleMap => Transform::NibbleMap,
            TransformArg::Identity => Transform::Identity,
        }
    }

    fn short(self) -> &'static str {
        match self {
            TransformArg::Xor51 => "xor51",
            TransformArg::CrazyMask => "crazy",
            TransformArg::RotateLeft => "rotl",
            TransformArg::NibbleMap => "nib",
            TransformArg::Identity => "id",
        }
    }
}

/// Draw `k` distinct input bytes for a finite-map instance. Deterministic in
/// `(seed, range, k)`: bytes come from a domain-tagged SHA-256 stream, are
/// projected into the range class, and deduplicated in draw order.
pub fn draw_inputs(k: usize, range: RangeClass, seed: u64) -> Vec<u8> {
    let mut out: Vec<u8> = Vec::with_capacity(k);
    let mut counter = 0u32;
    while out.len() < k {
        let block = hash_serialized(
            "malbolge-rungs:v0:generated-finite-map-inputs",
            &(seed, range.name().to_string(), counter),
        );
        for &byte in block.0.iter() {
            let b = range.apply(byte);
            if !out.contains(&b) {
                out.push(b);
                if out.len() == k {
                    break;
                }
            }
        }
        counter += 1;
    }
    out
}

fn default_program_len(k: usize) -> u64 {
    (256 * k as u64).clamp(512, 4096)
}

/// A generated instance: the rung itself plus advisory provenance blocks.
#[derive(Debug, Serialize)]
pub struct GeneratedRung {
    #[serde(flatten)]
    pub rung: Rung,
    pub generator: GeneratorInfo,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dispatch_feasibility: Option<FeasibilityScore>,
}

#[derive(Debug, Serialize)]
pub struct GeneratorInfo {
    pub schema: &'static str,
    pub command: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub seed: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub range: Option<RangeClass>,
}

#[derive(Debug, Serialize)]
pub struct FeasibilityScore {
    #[serde(flatten)]
    pub report: FeasibilityReport,
    pub difficulty_class: String,
}

/// Mint a finite-map instance.
pub fn generate_finite_map(
    k: usize,
    range: RangeClass,
    seed: u64,
    transform: TransformArg,
    max_program_len: Option<u64>,
    max_steps_per_case: u64,
    skip_feasibility: bool,
) -> anyhow::Result<GeneratedRung> {
    anyhow::ensure!(
        (2..=32).contains(&k),
        "k must be in 2..=32 (got {k}); the {} range holds {} distinct bytes",
        range.name(),
        range.domain_size()
    );
    let inputs = draw_inputs(k, range, seed);
    let id = format!("GEN.FM.{}-k{}-{}-s{}", transform.short(), k, range.name(), seed);
    let score = if skip_feasibility {
        None
    } else {
        let report = feasibility(&inputs);
        let class = report.difficulty_class().to_string();
        Some(FeasibilityScore {
            report,
            difficulty_class: class,
        })
    };
    let rung = Rung {
        id: id.clone(),
        title: format!(
            "Generated finite map: {} over {} {}-range bytes (seed {})",
            transform.short(),
            k,
            range.name(),
            seed
        ),
        level: 2,
        status: "Generated".to_string(),
        family: Family::FiniteMap,
        transform: transform.to_transform(),
        finite_map_inputs: inputs,
        output_bytes: 1,
        cases: k as u32,
        // Fixed inputs, so one epoch is definitive.
        min_epochs: None,
        min_correct_cases: None,
        max_program_len: max_program_len.unwrap_or_else(|| default_program_len(k)),
        max_steps_per_case,
        max_output_len: 1,
        max_memory_cells: classic_malbolge::CLASSIC_MEMORY_CELLS,
        purpose: format!(
            "Procedurally generated training instance (not part of the public reference \
             ladder). Deterministic: regenerate with `malbolge-rungs generate-rung \
             finite-map --k {} --range {} --seed {} --transform {}`.",
            k,
            range.name(),
            seed,
            transform.short()
        ),
    };
    Ok(GeneratedRung {
        rung,
        generator: GeneratorInfo {
            schema: GENERATOR_SCHEMA,
            command: format!(
                "generate-rung finite-map --k {} --range {} --seed {} --transform {}",
                k,
                range.name(),
                seed,
                transform.short()
            ),
            seed: Some(seed),
            range: Some(range),
        },
        dispatch_feasibility: score,
    })
}

/// Mint a coverage instance (all 256 single-byte inputs, pass at `threshold`).
pub fn generate_coverage(
    threshold: u32,
    transform: TransformArg,
    max_program_len: u64,
    max_steps_per_case: u64,
) -> anyhow::Result<GeneratedRung> {
    anyhow::ensure!(
        (1..=256).contains(&threshold),
        "threshold must be in 1..=256 (got {threshold})"
    );
    let id = format!("GEN.C.{}-cov{}", transform.short(), threshold);
    let rung = Rung {
        id: id.clone(),
        title: format!(
            "Generated coverage rung: {} correct on ≥ {} of 256 inputs",
            transform.short(),
            threshold
        ),
        level: 2,
        status: "Generated".to_string(),
        family: Family::CoverageTransform,
        transform: transform.to_transform(),
        finite_map_inputs: Vec::new(),
        output_bytes: 1,
        cases: 256,
        min_correct_cases: Some(threshold),
        min_epochs: None,
        max_program_len,
        max_steps_per_case,
        max_output_len: 1,
        max_memory_cells: classic_malbolge::CLASSIC_MEMORY_CELLS,
        purpose: format!(
            "Procedurally generated coverage instance (not part of the public reference \
             ladder). All 256 single-byte inputs are enumerated; the program passes with \
             at least {threshold} exact one-byte outputs; failures elsewhere are \
             tolerated. Regenerate with `malbolge-rungs generate-rung coverage \
             --threshold {threshold} --transform {}`.",
            transform.short()
        ),
    };
    Ok(GeneratedRung {
        rung,
        generator: GeneratorInfo {
            schema: GENERATOR_SCHEMA,
            command: format!(
                "generate-rung coverage --threshold {threshold} --transform {}",
                transform.short()
            ),
            seed: None,
            range: None,
        },
        dispatch_feasibility: None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn draw_inputs_is_deterministic_and_distinct() {
        let a = draw_inputs(12, RangeClass::Low, 7);
        let b = draw_inputs(12, RangeClass::Low, 7);
        assert_eq!(a, b);
        let mut sorted = a.clone();
        sorted.sort_unstable();
        sorted.dedup();
        assert_eq!(sorted.len(), 12, "inputs must be distinct");
        assert!(a.iter().all(|&x| x <= 0x3f));

        let hi = draw_inputs(8, RangeClass::High, 7);
        assert!(hi.iter().all(|&x| x >= 0x80));
        assert_ne!(draw_inputs(8, RangeClass::High, 8), hi, "seed must matter");
    }

    #[test]
    fn generated_rung_round_trips_through_rung_schema() {
        let g = generate_finite_map(4, RangeClass::Mixed, 42, TransformArg::Xor51, None, 2048, true)
            .unwrap();
        let json = serde_json::to_string_pretty(&g).unwrap();
        let rung: Rung = serde_json::from_str(&json).unwrap();
        assert_eq!(rung.id, g.rung.id);
        assert_eq!(rung.finite_map_inputs, g.rung.finite_map_inputs);
        assert_eq!(rung.cases, 4);
        assert_eq!(rung.max_program_len, 1024);

        let c = generate_coverage(40, TransformArg::Xor51, 4096, 2048).unwrap();
        let json = serde_json::to_string_pretty(&c).unwrap();
        let rung: Rung = serde_json::from_str(&json).unwrap();
        assert_eq!(rung.min_correct_cases, Some(40));
        assert_eq!(rung.cases, 256);
    }
}
