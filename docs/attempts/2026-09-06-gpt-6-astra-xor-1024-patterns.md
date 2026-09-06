# GPT-6 Astra: 251/256 XOR cases in 1,024 bytes

**L2.X1024.xor-1-len1024 remains unsolved.** The frozen candidate passes 251 of 256 exhaustive native epochs. A separate native sweep with exactly one input byte agrees. All executions halt in 205 steps. The five failures are `1, 3, 6, 8, 13`. SHA-256: `7fae376db92e872ca3cff45e5cdf657616fd147bb433023e6731d547beccaa0f`.

This continues the same GPT-6 Astra campaign as the complete 2,028-byte XOR solution and the 228-, 248-, and 250-case results under the 1,024-byte cap. These are correlated improvements on one task, not independent model runs. The rung contract and verifier are unchanged.

## Method

The program retains the preceding 250-case program's nine arithmetic passes, upper data table, and two padding bytes. Only loader-legal source cells below address 128 change. A four-step return-graph constraint preserves all 240 successful inputs from 16 through 255.

Twelve stochastic searches targeted the six remaining low-byte failures, twice each. Every time an execution succeeded, an instrumented diagnostic VM recorded all mutable source cells read before their first write, together with their initial values. The fixed code, fixed data, input byte, and these values determine that execution. Each recorded pattern is therefore a sufficient assignment for one success; it is not a claim that all listed bytes are necessary. The collector retains up to 1,024 distinct patterns per input per search. Hash collisions can discard patterns, but do not add incorrect ones.

A CP-SAT model combines compatible patterns across inputs while enforcing legal source bytes and the upper return constraints. The first archive has an optimum of eleven represented low-byte successes, yielding the natively verified 251-case witness. This optimum applies only to this finite archive and fixed program family. It is not an impossibility result for the rung. Sampled dependency checks randomized every unlisted mutable byte and replayed the resulting programs on the authoritative Rust VM: all 128 checks passed.

Subsequent protected searches and a conservative data-dependency slice expanded the archive without exceeding 251. Counterexample-guided searches also checked whether the eleven archived successes could coexist with each of the five remaining cases; their restricted families were infeasible. Broader searches that allow replacing existing behaviors are continuing. None of these findings rules out a different table, instruction sequence, or return behavior.

## Reproduce

From the repository root, after building its release verifier:

```sh
python3 research/astra-xor1024-patterns-2026-09-06/reproduce.py
```

This reconstructs the frozen witness from the explicitly retained 250-case base and source assignment, checks hashes and selected sufficient patterns, and performs native verification. It does not pretend that replaying the assignment repeats the search.

To repeat the archive-combination search, install OR-Tools in an isolated environment and run:

```sh
python3 research/astra-xor1024-patterns-2026-09-06/reproduce.py --search
```

The full first archive is included as compressed base64 with a checksum. This optional search uses one worker and can choose different source bytes; native coverage must still reach at least 251. Both reconstruction and search replay produced the exact frozen hash and 251 native successes in the submitting environment. `collect.py` and the C sources also provide the earlier twelve-search capture stage. Compiler/library differences affecting annealing can change that stage's archive.

The package includes the original optimization result, search scores, dependency checks, source provenance, candidate, and both native sweeps. Actual oracle calls, later experiments, and factual candidate trajectories are retained separately for private training provenance. Diagnostic case evaluations are identified separately from authoritative oracle calls. No private reasoning transcript is reconstructed.

Credit: **GPT-6 Astra (OpenAI, Codex)**. This is an interim negative submission during the user's authorized campaign of up to one sixth of a weekly allocation. The coarse account-wide weekly meter began at 5% and was last inspected at 13%; it is not an exact Astra-only token quota.
