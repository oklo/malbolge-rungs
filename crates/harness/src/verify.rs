//! The core verification loop: run a candidate program on the native
//! Classic-Malbolge-51 VM over a rung's derived cases and apply the rung's
//! rule:
//!
//! * Non-coverage rungs: every case must halt (native) and produce the exact
//!   expected output. Any mismatch or non-halt fails the rung.
//! * Coverage rungs: a case counts as correct when it halts (or succeeds) with
//!   the exact expected output; per-case runtime failures are tolerated and
//!   simply do not count. The rung passes when the number of correct cases
//!   reaches `min_correct_cases`.
//!
//! Only the native backend is ever used — it is the sole ground truth.

use classic_malbolge::{
    ClassicExecutionLimits, ClassicExecutionStatus, ClassicMalbolgeExecutor, NativeClassicBackend,
};

use crate::challenge::{derive_cases, derive_seed};
use crate::types::Rung;

#[derive(Clone, Debug, PartialEq, serde::Serialize)]
pub struct CaseResult {
    pub index: u32,
    pub input_hex: String,
    pub expected_hex: String,
    pub observed_hex: Option<String>,
    pub status: String,
    pub correct: bool,
}

#[derive(Clone, Debug, serde::Serialize)]
pub struct EpochResult {
    pub epoch: u32,
    pub seed_hex: String,
    pub passed: bool,
    pub correct_cases: u32,
    pub total_cases: u32,
    /// Failure reason for a non-passing epoch (`None` when passed).
    pub failure: Option<String>,
    pub cases: Vec<CaseResult>,
}

#[derive(Clone, Debug, serde::Serialize)]
pub struct VerifyOutcome {
    pub rung_id: String,
    pub passed: bool,
    pub coverage: bool,
    pub required_correct: u32,
    pub epochs: Vec<EpochResult>,
}

fn limits_for(rung: &Rung) -> ClassicExecutionLimits {
    ClassicExecutionLimits {
        max_steps: rung.max_steps_per_case,
        max_output_len: rung.max_output_len,
        max_program_len: rung.max_program_len,
        max_memory_cells: rung.max_memory_cells,
    }
}

/// Verify a candidate program against a rung over `epochs` deterministic seeds.
/// The rung passes only if every epoch passes.
pub fn verify_rung(rung: &Rung, program: &[u8], epochs: u32) -> VerifyOutcome {
    let backend = NativeClassicBackend;
    let limits = limits_for(rung);
    let coverage = rung.is_coverage();
    let required = rung.required_correct();

    let mut epoch_results = Vec::new();
    let mut all_passed = true;

    for epoch in 0..epochs.max(1) {
        let seed = derive_seed(&rung.id, epoch);
        let cases = derive_cases(rung, &seed, epoch);
        let mut case_results = Vec::with_capacity(cases.len());
        let mut correct_cases = 0u32;
        let mut failure: Option<String> = None;

        for case in &cases {
            let report = backend.execute(program, &case.input, &limits);
            let (observed_hex, status, correct) = match report {
                Ok(report) => {
                    let halted_or_success = matches!(
                        report.status,
                        ClassicExecutionStatus::Halted | ClassicExecutionStatus::Success
                    );
                    let output_matches = report.output == case.expected_output;
                    let correct = if coverage {
                        halted_or_success && output_matches
                    } else {
                        // Native execution must halt for a non-coverage pass.
                        report.status == ClassicExecutionStatus::Halted && output_matches
                    };
                    (
                        Some(hex::encode(&report.output)),
                        format!("{:?}", report.status),
                        correct,
                    )
                }
                Err(err) => (None, format!("Error: {err}"), false),
            };

            if correct {
                correct_cases += 1;
            } else if !coverage && failure.is_none() {
                failure = Some(format!(
                    "case {} mismatch: expected {}, got {} (status {})",
                    case.index,
                    hex::encode(&case.expected_output),
                    observed_hex.clone().unwrap_or_else(|| "<none>".to_string()),
                    status,
                ));
            }

            case_results.push(CaseResult {
                index: case.index,
                input_hex: hex::encode(&case.input),
                expected_hex: hex::encode(&case.expected_output),
                observed_hex,
                status,
                correct,
            });
        }

        let passed = if coverage {
            let ok = correct_cases >= required;
            if !ok {
                failure = Some(format!(
                    "coverage below threshold: {correct_cases} correct, {required} required"
                ));
            }
            ok
        } else {
            failure.is_none()
        };

        if !passed {
            all_passed = false;
        }

        epoch_results.push(EpochResult {
            epoch,
            seed_hex: seed.to_hex(),
            passed,
            correct_cases,
            total_cases: cases.len() as u32,
            failure,
            cases: case_results,
        });
    }

    VerifyOutcome {
        rung_id: rung.id.clone(),
        passed: all_passed,
        coverage,
        required_correct: required,
        epochs: epoch_results,
    }
}
