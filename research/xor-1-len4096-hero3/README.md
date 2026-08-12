# hero3 — L2.R0d.xor-1-len4096

Builds on `research/xor-1-len4096-hero2/` (which builds on hero1 and push).

* `hero10.c` — hero2's `hero9.c` plus three new modes:
  * `-reach -rlo A -rhi B` — can input b's block move C into [A,B]? Used to test
    whether the 4096-byte cap buys private code space past the block region.
  * `-desc` — the **descending decomposition**. Execution runs forward and d can
    never exceed ~126+stepcap (MOVD reads a program byte <= 126), so block b's
    own cells are read only by inputs LOWER than b.  Sweeping descending makes
    witness choice conflict-free above the shared window, and the acceptance
    gate becomes "no damage to inputs above b" instead of prior art's global
    delta >= 0 — which rejected exactly the productive trades.
  * `-window -lo L -hot H` — coordinate search over the shared window only,
    with `-desc` as the repair operator.  This is hero1's/hero2's "decomposed
    objective", made exact.
  * `-tails` — exhaustive sweep of the 64 crazy-tail families (flagged untried
    by both hero1 and hero2).  Not run to completion here; see the report.
* `fleet5.sh` — the run that produced the candidate (10 window searches).
* `fleet4.sh` — the first, over-deep configuration; kept because its failure is
  the point (see the report's note on step caps).
* `nc.sh`, `one.sh` — all-256 native measurement (the only honest score).
* `cand.mal` — the shipped candidate.
* `stride.py` — the proof that stride 9 is forced under the 4096-byte cap.
* `runs/` — logs.
