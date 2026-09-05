//! Curated presentation, separate from the versioned evaluator contracts.
use crate::types::{Family, Rung};
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize)]
pub struct Ladder {
    pub schema: String,
    pub revision: String,
    pub ordering: String,
    pub bands: Vec<Band>,
    pub rungs: Vec<Placement>,
}
#[derive(Debug, Deserialize, Serialize)]
pub struct Band {
    pub id: String,
    pub number: String,
    pub title: String,
    pub description: String,
}
#[derive(Debug, Deserialize, Serialize)]
pub struct Placement {
    pub rung_id: String,
    pub band: String,
    pub title: String,
    pub summary: String,
    pub calibration: String,
    pub rationale: String,
}
pub fn load_ladder() -> Ladder {
    serde_json::from_str(include_str!("../../../leaderboard/ladder.json"))
        .expect("ladder.json is valid")
}

/// Describe exactly which input evidence a pass supplies. Even a first-byte
/// sweep supplies a public suffix, so it is not exhaustive over VM input strings.
#[derive(Debug, Serialize)]
pub struct Evidence {
    pub label: String,
    pub detail: String,
    pub score_unit: &'static str,
}
pub fn evidence(r: &Rung) -> Evidence {
    let (label, detail, score_unit) = match r.family {
        Family::FiniteMap => (format!("{} fixed inputs", r.cases),
            "Every listed one-byte input is tested. This is the complete finite-map domain.".into(), "listed inputs"),
        Family::CoverageTransform => ("All 256 input bytes".into(),
            format!("Every one-byte input is tested; at least {} exact outputs with a clean halt are required. Other inputs may fail.", r.required_correct()), "input bytes"),
        Family::HashPrefix => (format!("{} public lookup rows", r.cases * r.required_epochs()),
            "Fixed public inputs and target bytes. Targets depend on a seed the program does not receive. Passing measures finite lookup construction, not hash computation. The attempt score reports the worst epoch; all epochs must pass.".into(), "cases in worst epoch"),
        Family::Stream => (format!("{} public stream cases", r.cases * r.required_epochs()),
            format!("Public deterministic inputs of {}–{} bytes. Exact whole-output match and halt are required. Passing does not establish unseen-length generalization or prove iteration. The attempt score reports the worst epoch.", r.min_input_len.unwrap_or(1), r.max_input_len.unwrap_or(1)), "cases in worst epoch"),
        _ if r.sweeps_first_byte() => ("256-value first-byte sweep".into(),
            format!("Every first-byte value is tested for each of {} cases over 256 epochs. The remaining input bytes are public deterministic samples. This does not exhaust all input strings{}.", r.cases, if r.output_bytes > 1 { " or all multi-byte tuples" } else { " or prove suffix independence" }), "cases across the sweep"),
        _ => ("Public example suite".into(),
            "Fixed public examples, with exact output and halt required. Canonical copying solutions may be more general than the tested suite; the suite alone does not establish that.".into(), "cases in worst epoch"),
    };
    Evidence {
        label,
        detail,
        score_unit,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn presentation_covers_each_contract_once_in_contiguous_bands() {
        let ladder = load_ladder();
        let board = crate::leaderboard::load_leaderboard();
        let reg = crate::registry::load_registry();
        let ids: std::collections::BTreeSet<_> =
            ladder.rungs.iter().map(|p| p.rung_id.as_str()).collect();
        assert_eq!(ids.len(), ladder.rungs.len());
        assert_eq!(ids, reg.iter().map(|r| r.id.as_str()).collect());
        assert_eq!(board.len(), reg.len());
        let mut previous_band = 0;
        for (i, rec) in board.iter().enumerate() {
            assert_eq!(rec.rank, Some(i as u32 + 1));
            let p = ladder
                .rungs
                .iter()
                .find(|p| p.rung_id == rec.rung_id)
                .unwrap();
            let band = ladder.bands.iter().position(|b| b.id == p.band).unwrap();
            assert!(band >= previous_band, "band order must remain contiguous");
            previous_band = band;
        }
    }
    #[test]
    fn partial_sweeps_and_lookups_are_not_labeled_exhaustive() {
        let r = crate::registry::find_rung("L3.R0.reverse-2-multicase").unwrap();
        assert!(evidence(&r).detail.contains("does not exhaust"));
        let r = crate::registry::find_rung("L5.R1.future-hash-prefix").unwrap();
        assert_eq!(evidence(&r).label, "20 public lookup rows");
        assert!(evidence(&r).detail.contains("not hash computation"));
    }
    #[test]
    fn xor_milestones_change_only_identity_and_length_budget() {
        let base = crate::registry::find_rung("L2.R0d.xor-1-len4096").unwrap();
        let normalize = |r: Rung| {
            let mut v = serde_json::to_value(r).unwrap();
            for key in ["id", "title", "purpose", "max_program_len"] {
                v.as_object_mut().unwrap().remove(key);
            }
            v
        };
        for cap in [2048, 1024, 512] {
            let r = crate::registry::find_rung(&format!("L2.X{cap}.xor-1-len{cap}")).unwrap();
            assert_eq!(r.max_program_len, cap);
            assert_eq!(normalize(r), normalize(base.clone()));
        }
    }
}
