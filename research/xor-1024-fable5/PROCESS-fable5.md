# Process log: Fable 5 run 4 — L2.X1024.xor-1-len1024

Solver: Fable 5 (Claude Code), model claude-fable-5, Anthropic. Date 2026-09-07.
Native evaluator: `malbolge-rungs verify --rung L2.X1024.xor-1-len1024 --epochs 256`
at scratch-clone head 51f081b. Trace dir: MALBOLGE_RUNGS_TRACE_DIR set for all
oracle calls.

## Step 1 — frontier reproduction (native)

- astra-xor1024-compact `candidate.mal`: **252/256 native**, fails {76,117,135,214},
  matching its record exactly.
- Rebuilt the compact DP (`biased243_model.c`, cc -O3): reproduces upper_score
  252 for the retained masks [386,80,108,146,278,272,20,7] and reassembles the
  byte-identical program (same sha256 fbbc3d4f…). Pipeline calibrated end-to-end.
- One DP evaluation ≈ 0.8 s single-core.

## Step 2 — schedule sweep (superseded by Step 3 finding)

`sweep.c`: 8-thread anneal over per-pass CRAZY/ROT/NOP mask schedules (6..8
passes) with the exact DP as objective, seeded from the four corpus schedules.
~9k schedules evaluated before being killed in favor of the joint search below;
nothing above 252 appeared. (hi.jsonl retains every eval ≥250.)

## Step 3 — the decisive measurement: the return alphabet binds, not the arithmetic

With the v5 return alphabet UNRESTRICTED (all 8 ops at all 94 residues), the
retained schedule's exact DP scores **256/256** (`/tmp/allow_all.txt` run of the
unmodified astra model). The affine record's "returns bind, arithmetic doesn't"
transfers to the compact family in the sharpest possible form: the alphabet is
the whole remaining problem at this cap.

## Step 4 — route model, validated bit-for-bit

Reverse-derived `allowed.txt`: a v5 byte is allowed iff the D-chain
d -> m[d]+1 from v5+1 reaches the absorbing root 41 within **6** MOVDs (the 7th
retop MOVD is deliberate absorbing slack; layout.json "depth: 6"), where memory
is the true post-prefix state (captured by an exact diagnostic VM at the first
pass boundary, C=139), and the walk never enters an input-dependent cell
({42,54,61,62,71,72}) or the table (>=244). This reproduces the reference
allowed.txt with **0 diffs over all 94 residues**.

Two structural notes with consequences:
- Route hops satisfy d = w+1 <= 127, so routes can never reach the pass code
  (>=134): the alphabet is schedule-independent, and boundary evolution is
  irrelevant (all route-reachable cells are stable after the prefix runs once).
- Absorption at exactly depth 7 is rejected by the reference; only <=6 counts.

Depth variants derived and priced: depth 5 = 368/752 alphabet bits but the same
8-pass fit (retlen 8 saves too little); depth 4 = 200 bits, buys a 9th pass but
strands ~16 inputs on 6 empty residues under the current pin set. Neither
dominates depth 6 head-on.

## Step 5 — the router is 53 free cells; wildcard bound

Prefix read-set captured over all 256 inputs (union): the prefix reads low cells
{0,42,43,44,45,47,54,56,57,58,61,62,63,71,72,73}. The free router cells — never
executed, never prefix-read, input-independent, loader-constrained to 8 bytes
each — are the 53 cells listed in freecells.json.

Wildcard upper bound (every route through a free cell treated as satisfiable):
alphabet 592/752 bits, DP = **254**, per-input reachability 256/256 with no dead
inputs. So: (a) the free-cell router can lift 252 -> at most 254 under the
retained schedule; (b) the residual loss is neighbor sharing, which is
schedule-dependent; (c) the search must be joint over (schedule x router).

## Step 6 — joint anneal (running)

`routesearch.c`: 8-thread anneal over (8-pass mask schedule x 53-cell router
assignment); objective = exact DP under the alphabet each assignment induces
(alphabet re-derived per candidate; schedule-independence of routes makes this
sound); every eval >=253 logged to rt_hi.jsonl; every new best assembled and
written durably (rt_best_N.mal/.av).

## Step 7 — escape repair: out-of-family per-input fixes (native +1)

The DP's family prescribes v5 in the routed alphabet. An out-of-alphabet v5
sends D off the return graph while C still walks the fixed code — the remaining
passes then read whatever D traverses, including implicit crazy fill (words
> 242, exactly the large operands the low-cap analyses lacked). `repair.c`
enumerates all 8^7 window assignments for a failing input under FULL exact
semantics with neighbor re-verification. On the 252 candidate: input 214 has
two clean escapes; 76/117/135 have none within their own window. Applying
[58,76,120,56,90,53,71] at window(214):

**cand253.mal — 253/256 native (verify --epochs 256), fails {76,117,135} — new
frontier for this rung (prior best 252).**

## Step 8 — instrumented two-level escapes + the 255 envelope

- `escape2.c scan`: logs which mutable low cells failing escape runs read;
  gates for 76: {68,49,33,67,40,60,53}; 117: {59,49,40,33,46}; 135: {59,40,33,49}.
  `escape2 joint`: window x two gate cells (134M exact sims per straggler),
  every hit filtered by an all-256 exact-model sweep (calibrated: baseline
  reproduces 253). Running for (76: 68,49), (117: 59,49), (135: 59,40).
- The wildcard-envelope schedule sweep (fixed 592-bit alphabet) found
  masks [338,3,272,313,150,24,16,68] with DP = **255** under the wildcard
  alphabet — the compact family is NOT capped at 254; an F-SLS instance now
  targets realizing that schedule's alphabet (out255/).

## Step 9 — negatives that close the run's search directions

- Realizability audit of the wildcard alphabet: exact route BFS (F cells as
  8-way choices, validated by finding routes for known-allowed bits) shows
  **0 of the 96 wildcard-only bits are realizable**. allowed.txt's 496 bits are
  exactly the free-cell-optimal alphabet; the router axis is closed. The
  255-envelope schedule was a mirage of the optimistic bound.
- Escape joints (window x two gate cells, 134M exact sims each, all-256 sweep
  filter): 76 x {68,49}, 117 x {59,49}, 135 x {59,40}, 135 x {33,49} — all
  zero hits.
- Stateful/patterns family low-16: single-window exhaustive escapes for
  {1,3,6,8,13} on the 251 candidate — zero hits (independently confirms the
  archive-completeness of the patterns record at this level).
- Tail-op variants ((39,62),(62,68),(68,62),(68,68),...): all <= 252 on the
  retained schedule; (62,62) is right.
- Second distinct 252-schedule found ([299,392,145,414,338,16,86,70], fails
  {25,122,177,217}, disjoint from the retained's set); none of its four
  failures single-window repairable. Continuous harvest->repair loop left
  running (autoloop.sh) to compose 254+ from schedule diversity if it exists.

## Step 10 — the shipped result

`cand253.mal` = astra compact 252 + the input-214 escape
([58,76,120,56,90,53,71] at window(214)). Native `verify --epochs 256`: 253/256,
fails {76,117,135}; one-byte native sweep agrees exactly (no suffix
dependence); sha256 ac3277f3fd531fee9a70aff7e0b70e344b6c77a3acda5293a0d39d944ac2beb7,
1016 bytes. New frontier on this rung (prior best 252).
