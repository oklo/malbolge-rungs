//! Challenge-case derivation.
//!
//! The challenge seed derives deterministically from the rung id and an epoch
//! index, so verification is reproducible and re-runnable anywhere.
//!
//! The seed only affects the hash-derived inputs of the `EchoPrefix`,
//! `HashPrefix`, and `Transform` families. The `FiniteMap` and
//! `CoverageTransform` families derive their inputs independently of the seed
//! (fixed input list / full 256-byte enumeration). Running several epochs
//! exercises several seeds, which guards echo/transform checks against
//! single-input overfitting.
//!
//! The hash domain strings below are frozen protocol constants: their exact
//! bytes (historical spellings included) define the derived cases, and
//! renaming them would silently re-derive every hash-dependent rung.

use crate::hashing::{hash_serialized, Hash32};
use crate::types::{ChallengeCase, Family, Rung, Transform};

/// Deterministic per-rung, per-epoch challenge seed.
pub fn derive_seed(rung_id: &str, epoch: u32) -> Hash32 {
    hash_serialized(
        "malbolge-rungs:v0:challenge-seed",
        &(rung_id.to_string(), epoch),
    )
}

/// Derive the full set of challenge cases for a rung under a given seed.
/// Mirrors the source `derive_challenge_cases`.
pub fn derive_cases(rung: &Rung, seed: &Hash32, epoch: u32) -> Vec<ChallengeCase> {
    let mut cases = Vec::with_capacity(rung.cases as usize);
    for index in 0..rung.cases {
        let input = match rung.family {
            Family::FiniteMap => rung
                .finite_map_inputs
                .get(index as usize)
                .copied()
                .map(|byte| vec![byte])
                .unwrap_or_default(),
            // Coverage cases enumerate the full single-byte domain in order,
            // independent of the challenge seed.
            Family::CoverageTransform => vec![(index % 256) as u8],
            // Stream: draw the LENGTH from the seed too, so the program cannot
            // be written against a length it knows in advance.
            Family::Stream => {
                let lo = rung.min_input_len.unwrap_or(1).max(1);
                let hi = rung.max_input_len.unwrap_or(lo).max(lo);
                let len_hash = hash_serialized("malbolge-coin:mal51:v0:stream-len", &(*seed, index));
                let span = u32::from(hi - lo + 1);
                let len = lo + (u32::from(len_hash.0[0]) % span);
                let mut bytes = Vec::with_capacity(len as usize);
                let mut block = 0u32;
                while bytes.len() < len as usize {
                    let h = hash_serialized(
                        "malbolge-coin:mal51:v0:stream-input",
                        &(*seed, index, block),
                    );
                    bytes.extend_from_slice(&h.0);
                    block += 1;
                }
                bytes.truncate(len as usize);
                bytes
            }
            _ => {
                let input_hash =
                    hash_serialized("malbolge-coin:mal51:v0:input", &(*seed, index));
                input_hash.0.to_vec()
            }
        };
        // Sweep rather than sample: epoch i pins case j's first byte to
        // (i + j) mod 256, so 256 epochs cover every byte for every case.
        let input = if rung.sweeps_first_byte() && !input.is_empty() {
            let mut swept = input;
            swept[0] = ((epoch as usize + index as usize) % 256) as u8;
            swept
        } else {
            input
        };
        let expected_output = derive_expected_output(seed, &input, index, rung);
        cases.push(ChallengeCase {
            index,
            input,
            expected_output,
        });
    }
    cases
}

fn derive_expected_output(seed: &Hash32, input: &[u8], index: u32, rung: &Rung) -> Vec<u8> {
    let width = rung.output_bytes as usize;
    let prefix: Vec<u8> = input.iter().take(width).copied().collect();
    match rung.family {
        Family::EchoPrefix => prefix,
        Family::HashPrefix => hash_serialized(
            "malbolge-coin:mal51:v0:hash-prefix",
            &(*seed, input.to_vec(), index),
        )
        .0
        .into_iter()
        .take(width)
        .collect(),
        Family::Transform | Family::FiniteMap | Family::CoverageTransform => {
            transform_bytes(&prefix, rung.transform)
        }
        // Computed over the whole input, not a fixed-width prefix — that is what
        // makes the output length unknown to the program in advance.
        Family::Stream => match rung.transform {
            Transform::Length => vec![(input.len() % 256) as u8],
            Transform::Checksum => {
                vec![input.iter().fold(0u8, |acc, b| acc.wrapping_add(*b))]
            }
            other => transform_bytes(input, other),
        },
    }
}

fn transform_bytes(input: &[u8], transform: Transform) -> Vec<u8> {
    match transform {
        Transform::Identity => input.to_vec(),
        Transform::Reverse => input.iter().rev().copied().collect(),
        Transform::XorMask => input.iter().map(|byte| byte ^ 0x51).collect(),
        Transform::CrazyMask => input
            .iter()
            .map(|byte| (classic_malbolge::crazy_word(u16::from(*byte), 0x51) % 256) as u8)
            .collect(),
        Transform::RotateLeft => input.iter().map(|byte| byte.rotate_left(1)).collect(),
        Transform::NibbleMap => input.iter().map(|byte| (byte << 4) | (byte >> 4)).collect(),
        // Whole-input transforms; handled by the Stream arm, which knows the
        // full input. Reaching here means a rung paired them with a
        // fixed-width family, where they have no meaning.
        Transform::Length => vec![(input.len() % 256) as u8],
        Transform::Checksum => vec![input.iter().fold(0u8, |acc, b| acc.wrapping_add(*b))],
    }
}
