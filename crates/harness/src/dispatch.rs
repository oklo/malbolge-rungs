//! Dispatch-feasibility estimator for finite-map rungs.
//!
//! Every known finite-map solution (map4, map6) starts the same way: a fixed
//! prelude reads the input byte x, applies an even-length chain of CRAZY
//! operations with constant operands, and jumps to the result, so each input
//! begins executing at its own address J(x) = crazy(...crazy(x, t1)..., tn).
//! Whether that first stage can *separate* a given input set — give every
//! input a distinct, usable landing address — is a cheap, deterministic proxy
//! for how hard the rung is. The map6→map8 evidence: map6 (solved) has
//! thousands of separating configs, map8 (open) has 39, and the map12-low and
//! map16 input sets have zero, meaning this whole dispatch family cannot even
//! start on them.
//!
//! The enumeration mirrors the construction published in the map6 rung notes:
//! a prelude of ten cells where cells 2..=8 each hold either a NOP or a CRAZY,
//! cell 9 always holds the final CRAZY, and each CRAZY's operand lives at cell
//! 40+p (p = the instruction's position), restricted to the ~8 bytes the
//! loader accepts at that cell. Chains of length 2 and 4 are enumerated; odd
//! chains are excluded because they leave the high trits of the ternary word
//! set (crazy(0,0) = 29524), landing J near 29,500 — far outside program
//! space. A config "separates" the input set when all J values are distinct
//! and the lowest landing clears the prelude's reserved cells (J >= 55).

use classic_malbolge::crazy_word;

/// The eight instruction codes of classic Malbolge, as residues mod 94.
const VALID_OPS: [i32; 8] = [4, 5, 23, 39, 40, 62, 68, 81];

/// Lowest landing address usable by a dispatch config: below this the landing
/// would fall inside the prelude / reserved operand cells.
const J_MIN_USABLE: u16 = 55;

/// Upper bound on landing addresses considered usable (matches the bound the
/// map6/map8 feasibility measurements used).
const J_MAX_USABLE: u16 = 1300;

/// The unique printable byte (33..=126) that decodes to `op` at `address`.
/// The loader computes (byte + address) mod 94 and accepts only the eight
/// instruction codes; the printable range is exactly 94 wide, so each opcode
/// has exactly one legal byte per address.
fn source_byte_for_op(op: i32, address: i32) -> u16 {
    let mut b = (op - address).rem_euclid(94);
    if b < 33 {
        b += 94;
    }
    b as u16
}

/// The eight loader-valid bytes at `address`, one per instruction code.
pub fn loader_valid_bytes(address: i32) -> [u16; 8] {
    let mut out = [0u16; 8];
    for (i, op) in VALID_OPS.iter().enumerate() {
        out[i] = source_byte_for_op(*op, address);
    }
    out
}

/// Feasibility of the even-CRAZY dispatch family for one input set.
#[derive(Clone, Debug, serde::Serialize)]
pub struct FeasibilityReport {
    /// The input bytes scored.
    pub inputs: Vec<u8>,
    /// Total dispatch configs enumerated (chain shapes × operand choices).
    pub configs_enumerated: usize,
    /// Configs where every input gets a distinct usable landing address.
    pub separating_configs: usize,
    /// Over separating configs: the largest minimum gap between two landing
    /// addresses. Bigger gaps leave more room for per-lane code; the map6
    /// campaign found min-gaps of ~7 workable and tight clusters hard.
    pub best_min_gap: Option<u16>,
    /// Over separating configs: the widest spread (Jmax - Jmin). Wide spreads
    /// give lanes room but can push pointer cells into executed regions.
    pub widest_spread: Option<u16>,
}

/// A coarse difficulty class derived from the separating-config count.
impl FeasibilityReport {
    pub fn difficulty_class(&self) -> &'static str {
        match self.separating_configs {
            0 => "wall (dispatch family cannot separate this input set)",
            1..=99 => "frontier (few separating configs; packing likely binds)",
            100..=999 => "hard (separation available, realization is the work)",
            _ => "workable (separation plentiful)",
        }
    }
}

/// Enumerate the even-CRAZY dispatch family over an input set and count
/// separating configs. Deterministic, no allocation beyond the report.
pub fn feasibility(inputs: &[u8]) -> FeasibilityReport {
    let mut enumerated = 0usize;
    let mut separating = 0usize;
    let mut best_min_gap: Option<u16> = None;
    let mut widest_spread: Option<u16> = None;

    // Chain positions: `extra` CRAZYs among cells 2..=8 plus the mandatory
    // final CRAZY at cell 9. extra ∈ {1, 3} → even chains of length 2 and 4.
    let mut position_sets: Vec<Vec<i32>> = Vec::new();
    for p in 2..=8 {
        position_sets.push(vec![p, 9]);
    }
    for a in 2..=8 {
        for b in (a + 1)..=8 {
            for c in (b + 1)..=8 {
                position_sets.push(vec![a, b, c, 9]);
            }
        }
    }

    let mut js: Vec<u16> = Vec::with_capacity(inputs.len());
    for cps in &position_sets {
        let alphabets: Vec<[u16; 8]> =
            cps.iter().map(|p| loader_valid_bytes(40 + p)).collect();
        // Odometer over the operand alphabets.
        let mut idx = vec![0usize; cps.len()];
        loop {
            enumerated += 1;
            js.clear();
            for &x in inputs {
                let mut a = x as u16;
                for (ai, alphabet) in alphabets.iter().enumerate() {
                    a = crazy_word(a, alphabet[idx[ai]]);
                }
                js.push(a);
            }
            js.sort_unstable();
            let distinct = js.windows(2).all(|w| w[0] != w[1]);
            if distinct && js[0] >= J_MIN_USABLE && js[js.len() - 1] <= J_MAX_USABLE {
                separating += 1;
                if js.len() >= 2 {
                    let min_gap = js.windows(2).map(|w| w[1] - w[0]).min().unwrap();
                    let spread = js[js.len() - 1] - js[0];
                    best_min_gap = Some(best_min_gap.map_or(min_gap, |b| b.max(min_gap)));
                    widest_spread = Some(widest_spread.map_or(spread, |w| w.max(spread)));
                }
            }
            // Advance the odometer.
            let mut carry = true;
            for slot in (0..idx.len()).rev() {
                if !carry {
                    break;
                }
                idx[slot] += 1;
                if idx[slot] == 8 {
                    idx[slot] = 0;
                } else {
                    carry = false;
                }
            }
            if carry {
                break;
            }
        }
    }

    FeasibilityReport {
        inputs: inputs.to_vec(),
        configs_enumerated: enumerated,
        separating_configs: separating,
        best_min_gap,
        widest_spread,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn loader_valid_bytes_are_printable_and_decode() {
        for addr in 0..200 {
            for b in loader_valid_bytes(addr) {
                assert!((33..=126).contains(&b));
                let code = (b as i32 + addr).rem_euclid(94);
                assert!(VALID_OPS.contains(&code), "addr {addr} byte {b}");
            }
        }
    }

    /// Cross-check against the counts measured during the map6 campaign
    /// (2026-08-01) with the original Python enumeration.
    #[test]
    fn reproduces_measured_separating_config_counts() {
        let map8 = [0x02, 0x06, 0x09, 0x30, 0x82, 0x6f, 0xa7, 0xc0];
        assert_eq!(feasibility(&map8).separating_configs, 39);

        let map12_hi = [
            0xa5, 0xe0, 0x90, 0x9c, 0x84, 0xa1, 0xbd, 0xc8, 0xbe, 0xf9, 0x86, 0xdd,
        ];
        assert_eq!(feasibility(&map12_hi).separating_configs, 115);

        let map12_low = [
            0x08, 0x37, 0x35, 0x1a, 0x2a, 0x32, 0x38, 0x2f, 0x0d, 0x18, 0x3b, 0x14,
        ];
        assert_eq!(feasibility(&map12_low).separating_configs, 0);

        let map16 = [
            0x02, 0x06, 0x09, 0x30, 0x82, 0x6f, 0xa7, 0xc0, 0xc5, 0xf6, 0x1c, 0x87,
            0xf0, 0x2d, 0x4a, 0x85,
        ];
        assert_eq!(feasibility(&map16).separating_configs, 0);
    }

    #[test]
    fn solved_rungs_have_plentiful_separation() {
        let map4 = [0x02, 0x06, 0x09, 0x30];
        let map6 = [0x02, 0x06, 0x09, 0x30, 0x82, 0x6f];
        assert!(feasibility(&map4).separating_configs > feasibility(&map6).separating_configs);
        assert!(feasibility(&map6).separating_configs > 39);
    }
}
