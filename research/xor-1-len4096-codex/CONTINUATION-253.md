# Codex continuation — `L2.R0d.xor-1-len4096`

This directory contains a native-verified **253/256** candidate and the search
programs that derived it from the inherited hero1/hero3 artifacts.

## Champion

`runs/round2-route9-desc-r0-o0.mal`

- length: 2605 bytes
- SHA-256: `38f593429e9ea02a07209e5ee9e732bcfccdac63845fd94a93d5c7c6df9c7a64`
- native all-byte score: **253/256**
- failures: `0 1 3`

Verify it with the canonical evaluator:

```sh
./target/release/malbolge-rungs verify \
  --rung L2.R0d.xor-1-len4096 \
  --program research/xor-1-len4096-codex/runs/round2-route9-desc-r0-o0.mal \
  --epochs 256 --json |
jq '{program:.results[0].program,
     program_len:.results[0].program_len,
     sha256:.results[0].program_sha256,
     correct:([.results[0].outcome.epochs[]|select(.passed)]|length),
     failures:[.results[0].outcome.epochs[]|select(.passed|not)|.epoch]}'
```

## Derivation

The inherited hero1 candidate scored 249/256 and failed
`0 1 3 8 9 151 255`. The productive path was:

1. `lengthscan_hero1.c` exhaustively scanned lengths 2305..4096 and all 64
   legal final-byte opcode pairs. Phase-aligned length 2605 retains all 249
   successes while providing writable extension space.
2. `route_hero1.c` routed byte 255 through that extension. A protected repair
   of the displaced byte 254 reached 250/256.
3. `joint150151_hero1.c` exactly crossed the coupled byte-150/151 witness
   families, reaching 251/256 at
   `runs/hero1-joint150151-short-o0-0.mal`.
4. An exact byte-8 route followed by `desc_hero1.c` reconstructed the other
   inputs while freezing byte 8. This exchanged byte 9 for byte 11 and stayed
   at 251/256.
5. Routing byte 11, then reconstructing with bytes 8 and 11 frozen, reached
   252/256 and left `0 1 3 9`.
6. Routing byte 9, then reconstructing with bytes 8, 9, and 11 frozen, reached
   the 253/256 champion. Twelve independently generated reconstruction
   variants reached the same score; several were checked natively.

The final three stages are a compatibility construction: the raw route is
allowed to damage already-solved inputs, and descending reconstruction restores
them while making the newly solved low input non-negotiable.

## Four-hour exact-neighborhood continuation

A final continuation attacked the three residual failures directly. It did not
improve the native 253/256 champion, but it closes several small neighborhoods
and preserves two new compatible basins:

- `single_mutation_scan.c`, `pair_mutation_scan.c`, and
  `triple_mutation_scan.c` exhaustively searched legal source edits. The
  champion is an exact Hamming-2 local maximum. Input 1 has a unique two-edit
  repair in the enumerated neighborhood (`66=67, 100=75`), scoring 209/256;
  its best exact triple scores 242/256. Input 3 has no one- or two-edit repair,
  and its best exact triple scores 234/256.
- Reconstructing the best input-1 triple while preserving its semantic result
  reaches 251/256, failing `0 3 8 10 145`. Exact four-edit branches and
  reconstruction repeatedly return to that same basin.
- A joint input-1/input-3 four-edit branch starts at 231/256. Exhaustive
  two-cell coordinate ascent improves it through 232 and 233 to 234/256, where
  `pair_improve_scan.c` proves another Hamming-2 fixed point. Reconstruction
  returns to the same 249/256 basin, failing `0 2 6 8 10 145 152`.
- The complementary exact five-edit partition is constructive: the unique
  two-edit input-1 repair followed by an exact three-edit input-3 repair solves
  both inputs simultaneously at 192/256. Descending reconstruction with both
  semantic locks reaches a native 246/256 tape, failing
  `0 2 7 8 9 11 13 14 144 154`; an exhaustive two-cell rescan finds no
  admissible improvement. The representative tapes are
  `runs/round3-pair-b1-plus-triple-b3.mal` and
  `runs/round3-exact-joint13-desc-o0.mal`.
- `prologue_prefix_scan.c` exhaustively checks the champion prologue at widths
  four and five, plus all width-six and width-seven suffixes from source cell
  1. Only the original width-four prefix retains 253/256; the best alternate
  tested prefixes solve at most four inputs. `prologue_sparse_scan.c` checks
  all 26,103 legal one- and two-cell edits in the 33-byte prologue; six make
  input 0 reachable, but none scores above 1/256.
- Corrected hero2 routing confirms that a byte-0-reachable architecture can
  solve input 0. The exact raw route scores 121/256 and its first monotone
  reconstruction reached 206/256. Recompiling the exact pair scanner against
  the corrected hero2 VM then produced an exhaustive protected ascent
  `206 -> 207 -> 208 -> 209 -> 210`; a final full two-cell rescan was empty.
  Feeding that seed back through the corrected reconstruction reached a
  native-verified **239/256** while preserving input 0, failing
  `1 3 4 5 8 9 10 11 12 13 14 15 16 27 252 254 255`. This materially narrows
  the architectural gap but remains below the old-prologue champion. The tape
  is `runs/round3-hero2-b0-210-desc-o4.mal`.
- Routing input 1 from that 239 tape while preserving input 0, then rebuilding
  with semantic locks on both 0 and 1, reaches a native-verified **235/256**
  tape. It fails
  `3 4 5 6 7 8 9 10 11 12 13 14 15 16 133 147 159 177 241 252 255`.
  An exhaustive 16-shard protected two-cell scan evaluated 23,479,869 legal
  pairs and found no improvement. The retained tape is
  `runs/round3-hero2-b0-b1-desc-o5.mal`.
- A less destructive exact three-cell input-1 repair scores 209/256 before
  reconstruction and reaches **237/256** afterward with inputs 0 and 1 still
  solved. It fails
  `3 4 5 8 9 10 11 12 13 14 15 16 144 145 146 235 252 254 255`.
  A second exhaustive protected two-cell scan evaluates 22,037,496 legal
  pairs without improvement. The representative native-verified tape is
  `runs/round3-hero2-b0-triple1-209-desc-o0.mal`.

The continuation also adds `crossover_scan.c`, `protected_route_anneal.c`, and
the exact scanners above. Every score quoted as native was checked with the
canonical Rust evaluator; raw-search scores used the same VM semantics and key
milestones were checked natively before further reconstruction.

## Reproduction

Build the principal tools:

```sh
cc -O3 -o research/xor-1-len4096-codex/lengthscan_hero1 \
  research/xor-1-len4096-codex/lengthscan_hero1.c
cc -O3 -o research/xor-1-len4096-codex/route_hero1 \
  research/xor-1-len4096-codex/route_hero1.c
cc -O3 -o research/xor-1-len4096-codex/desc_hero1 \
  research/xor-1-len4096-codex/desc_hero1.c
cc -O3 -o research/xor-1-len4096-codex/joint150151_hero1 \
  research/xor-1-len4096-codex/joint150151_hero1.c
```

The first-stage commands and the exact productive byte-8 route are:

```sh
./research/xor-1-len4096-codex/lengthscan_hero1 \
  -s research/xor-1-len4096-hero1/cand.mal \
  -o research/xor-1-len4096-codex/runs/hero1-length-best.mal \
  -lo 2305 -hi 4096

./research/xor-1-len4096-codex/route_hero1 \
  -s research/xor-1-len4096-codex/runs/hero1-correct-s4.mal \
  -o research/xor-1-len4096-codex/runs/hero1-routed255-o6.mal \
  -N 2605 -target 255 -lo 2323 -hi 2377 -span 8 \
  -steps 220 -nodes 3000000000 -order 6

./research/xor-1-len4096-codex/route_hero1 \
  -s research/xor-1-len4096-codex/runs/hero1-routed255-o6.mal \
  -o research/xor-1-len4096-codex/runs/hero1-routed254-after255-o0.mal \
  -N 2605 -target 254 -protect 255 -lo 2323 -hi 2377 -span 36 \
  -steps 220 -nodes 3000000000 -order 0

./research/xor-1-len4096-codex/joint150151_hero1 \
  -s research/xor-1-len4096-codex/runs/hero1-routed254-after255-o0.mal \
  -o research/xor-1-len4096-codex/runs/hero1-joint150151-short-o0-0.mal \
  -N 2605 -order1 0 -order2 0 -span1 12 -span2 12 \
  -nodes1 3000000000 -nodes2 3000000000

./research/xor-1-len4096-codex/route_hero1 \
  -s research/xor-1-len4096-codex/runs/hero1-joint150151-short-o0-0.mal \
  -o research/xor-1-len4096-codex/runs/round2-b8-own-o0.mal \
  -target 8 -lo 73 -hi 81 -span 9 -steps 220 \
  -nodes 3000000000 -order 0
```

The byte-11 and byte-9 milestones are retained in `runs/` alongside the final
tape. Their construction used the same `route_hero1`/`desc_hero1` pattern with
protected sets `{8,11}` and `{8,9,11}` respectively.

## Other tools and negative evidence

- `joint89_hero1.c` exactly enumerated 529 byte-8 witnesses and 13,542 byte-9
  witnesses on the 251 tape. It found 3,298 compatible pairs, but their best
  low-input coverage was only 12/18; direct joint repair is too destructive.
- `joint_low_hero1.c` hashes shared assignments to cross the champion's exact
  byte-8/9 witnesses with wide byte-1 or byte-3 route families. Multiple DFS
  order rotations, including several complete 65,536-witness prefixes, found
  no compatible triple. These are prefix-bounded results, not proofs.
- `joint13_hero1.c` directly crossed wide byte-1 and byte-3 route families.
  Across all 64 pairs of DFS order rotations, every tested signature family
  had zero hash-compatible pairs. Most families reached the 65,536-witness
  cap; the remainder reached the three-billion-node cap. This is again
  bounded-prefix evidence, but it localizes the incompatibility to required
  initial bytes in the shared window.
- A broad byte-1 route can be made, but its best protected reconstruction
  reached only 250/256. Forcing every opcode at the main shared address did not
  improve the champion. Broad byte-3 routes were still more destructive.
- A byte-0-reachable alternate prologue was protected and rebuilt to 227/256;
  it remains far below the old-prologue line. Byte 0 is unreachable under the
  champion's fixed prologue, so a full solution requires an architectural
  crossover rather than another local patch.
- `splice_delta.c` transplanted the champion's source delta onto independently
  phase-compatible 2887- and 3451-byte hero1 tapes. Both retained the same
  253/256 behavior, showing that the result is not tied to one exact tail
  length. Reassembling a byte-0-reachable swapped prologue around the preserved
  downstream structure reached 231/256, better than rebuilding that line from
  scratch but still well below the champion.
- At length 3451, input 1 can be routed through the old shared window to a
  genuinely private extension near address 3268. Eight exact DFS rotations
  found capped witness families; the least destructive witness changed 78
  source cells and scored a native-verified 59/256. A bounded descending pass
  reached 131/256 in the surrogate, but native verification scored it 130/256
  and showed that input 1 had been lost despite the surrogate trace lock. This
  establishes reachability while exposing both a large compatibility cost and
  a longer-tape edge case in the search model.
- `protected_anneal.c` preserves selected semantic routes while exploring
  reconstructions after a broad byte-1 or byte-3 route. Diversified annealing,
  protected annealing, and coordinate/descending searches did not exceed the
  champion.
- `trace.c`, `compatlow.c`, `protected_desc.c`, and the other small C programs
  are bounded diagnostics used to test local-repair hypotheses.

`runs/` is deliberately a scratch ledger as well as a result directory. The
champion above is the submission artifact; intermediate candidates preserve the
route and reconstruction history.

The narrative report is
[`docs/attempts/2026-08-13-codex-hero-runs-xor-1-len4096.md`](../../docs/attempts/2026-08-13-codex-hero-runs-xor-1-len4096.md).
