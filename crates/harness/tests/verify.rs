//! Integration tests: the whole point of the harness is that solved rungs
//! re-verify on the native VM, so that is exactly what CI checks.

use harness::leaderboard::verify_leaderboard;
use harness::registry::{find_rung, load_registry};
use harness::verify::verify_rung;

#[test]
fn registry_loads_all_rungs() {
    let reg = load_registry();
    assert!(reg.len() >= 28, "expected the full rung ladder, got {}", reg.len());
    // A couple of anchor rungs with known shapes.
    let fm1 = find_rung("L2.FM1.xor51-map4").expect("FM1 present");
    assert_eq!(fm1.finite_map_inputs, vec![0x02, 0x06, 0x09, 0x30]);
    let cov = find_rung("L2.C0.xor51-cov32").expect("cov32 present");
    assert_eq!(cov.min_correct_cases, Some(32));
    assert_eq!(cov.cases, 256);
}

#[test]
fn every_solved_leaderboard_entry_reverifies() {
    let (results, all_ok) = verify_leaderboard(3);
    assert!(!results.is_empty(), "leaderboard has at least one solved entry");
    for r in &results {
        assert!(r.passed, "{} ({}) failed re-verification: {}", r.rung_id, r.program, r.detail);
    }
    assert!(all_ok);
}

#[test]
fn wrong_program_fails_rung() {
    // The FM0 program does not satisfy FM1 (it only maps two inputs).
    let fm1 = find_rung("L2.FM1.xor51-map4").unwrap();
    let root = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");
    let fm0_prog = std::fs::read(format!("{root}/solutions/fm0/fm0-map2.mal")).unwrap();
    let outcome = verify_rung(&fm1, &fm0_prog, 1);
    assert!(!outcome.passed, "FM0 program must not pass FM1");
}

#[test]
fn generated_rung_verifies_end_to_end_on_native_vm() {
    // Mint an identity finite map, round-trip it through its JSON form (the
    // `--rung-file` path), and check the canonical echo program solves it on
    // the native VM — the full generate → serialize → load → verify pipeline.
    use harness::generate::{generate_finite_map, RangeClass, TransformArg};

    let generated =
        generate_finite_map(6, RangeClass::Mixed, 7, TransformArg::Identity, None, 2048, true)
            .unwrap();
    let json = serde_json::to_string(&generated).unwrap();
    let rung: harness::types::Rung = serde_json::from_str(&json).unwrap();

    let root = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");
    let echo = std::fs::read(format!("{root}/solutions/echo/echo-first-byte.mal")).unwrap();
    let outcome = verify_rung(&rung, &echo, 2);
    assert!(outcome.passed, "echo must solve a generated identity finite map");

    // Same instance under xor51 must NOT pass with the echo program.
    let generated =
        generate_finite_map(6, RangeClass::Mixed, 7, TransformArg::Xor51, None, 2048, true)
            .unwrap();
    let outcome = verify_rung(&generated.rung, &echo, 1);
    assert!(!outcome.passed, "echo must not solve a xor51 finite map");
}

#[test]
fn generation_is_deterministic_across_calls() {
    use harness::generate::{generate_finite_map, RangeClass, TransformArg};
    let a = generate_finite_map(12, RangeClass::High, 3, TransformArg::Xor51, None, 2048, true)
        .unwrap();
    let b = generate_finite_map(12, RangeClass::High, 3, TransformArg::Xor51, None, 2048, true)
        .unwrap();
    assert_eq!(a.rung.finite_map_inputs, b.rung.finite_map_inputs);
    assert_eq!(a.rung.id, b.rung.id);
}
