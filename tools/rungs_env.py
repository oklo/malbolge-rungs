"""Thin Python client for the malbolge-rungs native verification oracle.

Standard library only. This module contains no VM logic and cannot disagree
with the ground truth: every call shells out to the native `malbolge-rungs`
binary and returns its parsed JSON. Build it first:

    cargo build --release

Typical RL-loop usage:

    from tools.rungs_env import RungsOracle

    oracle = RungsOracle()                      # finds target/release or target/debug
    inst = oracle.generate_finite_map(k=7, range_class="low", seed=1234)
    passed, correct, total, envelope = oracle.score(program_bytes, rung_file=inst["path"])
    reward = correct / total                    # graded; `passed` is the binary reward

See ENVIRONMENT.md for the JSON contracts (schemas malbolge-rungs.verify.v1,
malbolge-rungs.generate-rung.v1, malbolge-rungs.feasibility.v1).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class OracleError(RuntimeError):
    """The binary failed for a reason other than a failing verification."""


class RungsOracle:
    def __init__(self, binary: str | None = None):
        if binary is None:
            for profile in ("release", "debug"):
                candidate = os.path.join(_REPO_ROOT, "target", profile, "malbolge-rungs")
                if os.path.exists(candidate):
                    binary = candidate
                    break
        if binary is None or not os.path.exists(binary):
            raise OracleError(
                "malbolge-rungs binary not found; run `cargo build --release` first"
            )
        self.binary = binary

    def _run(self, args: list[str], ok_codes: tuple[int, ...] = (0,)) -> str:
        proc = subprocess.run(
            [self.binary, *args], capture_output=True, text=True, cwd=_REPO_ROOT
        )
        if proc.returncode not in ok_codes:
            raise OracleError(
                f"malbolge-rungs {' '.join(args)} exited {proc.returncode}: "
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            )
        return proc.stdout

    # -- reward oracle -------------------------------------------------------

    def verify(
        self,
        programs: list[str],
        rung: str | None = None,
        rung_file: str | None = None,
        epochs: int = 1,
    ) -> dict:
        """Verify program file(s); returns the verify.v1 envelope.

        Exit code 1 (verification failed) is a valid result, not an error.
        """
        args = ["verify", "--json", "--epochs", str(epochs)]
        if rung is not None:
            args += ["--rung", rung]
        if rung_file is not None:
            args += ["--rung-file", rung_file]
        for p in programs:
            args += ["--program", p]
        return json.loads(self._run(args, ok_codes=(0, 1)))

    def score(
        self,
        program_bytes: bytes,
        rung: str | None = None,
        rung_file: str | None = None,
        epochs: int = 1,
    ) -> tuple[bool, int, int, dict]:
        """Score raw program bytes: (passed, correct_cases, total_cases, envelope).

        correct/total are taken from the worst epoch, so the graded reward
        never overstates a seed-dependent rung.
        """
        with tempfile.NamedTemporaryFile(suffix=".mal", delete=False) as f:
            f.write(program_bytes)
            path = f.name
        try:
            envelope = self.verify([path], rung=rung, rung_file=rung_file, epochs=epochs)
        finally:
            os.unlink(path)
        outcome = envelope["results"][0]["outcome"]
        worst = min(outcome["epochs"], key=lambda e: e["correct_cases"])
        return outcome["passed"], worst["correct_cases"], worst["total_cases"], envelope

    def execute(self, program: str, input_hex: str = "") -> dict:
        """Run a program once on the native VM (raw probe, no rung rule)."""
        return json.loads(
            self._run(["execute", "--program", program, "--input-hex", input_hex])
        )

    # -- instance generation -------------------------------------------------

    def generate_finite_map(
        self,
        k: int,
        range_class: str = "mixed",
        seed: int = 0,
        transform: str = "xor51",
        out: str | None = None,
    ) -> dict:
        """Mint a finite-map instance; returns the rung JSON (plus "path" if written)."""
        args = [
            "generate-rung", "finite-map",
            "--k", str(k), "--range", range_class,
            "--seed", str(seed), "--transform", transform,
        ]
        return self._generate(args, out)

    def generate_coverage(
        self, threshold: int, transform: str = "xor51", out: str | None = None
    ) -> dict:
        """Mint a coverage instance; returns the rung JSON (plus "path" if written)."""
        args = ["generate-rung", "coverage", "--threshold", str(threshold),
                "--transform", transform]
        return self._generate(args, out)

    def _generate(self, args: list[str], out: str | None) -> dict:
        if out is None:
            fd, out = tempfile.mkstemp(suffix=".rung.json")
            os.close(fd)
        self._run(args + ["--out", out])
        with open(out) as f:
            rung = json.load(f)
        rung["path"] = out
        return rung

    # -- difficulty estimation ------------------------------------------------

    def feasibility(
        self,
        inputs: list[int] | None = None,
        rung: str | None = None,
        rung_file: str | None = None,
    ) -> dict:
        """Dispatch-feasibility report (feasibility.v1) for an input set or rung."""
        args = ["feasibility", "--json"]
        if inputs is not None:
            args += ["--inputs", ",".join(f"{b:02x}" for b in inputs)]
        if rung is not None:
            args += ["--rung", rung]
        if rung_file is not None:
            args += ["--rung-file", rung_file]
        return json.loads(self._run(args))
