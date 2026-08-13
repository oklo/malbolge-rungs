/* Descending reconstruction for the 34-byte clean low-input prologue.
 *
 * prologue_phase_synth.c found a first-pass-equivalent prologue whose four
 * low inputs all survive the enciphered second pass.  low_phase_route.c then
 * installs an exact route for one of those inputs, usually disturbing many
 * independent high-input blocks.  This pass repairs those blocks from high
 * to low while preserving selected low routes semantically.
 */
#define RMAXCELL 128
#define ROUTE_HERO1_NO_MAIN
#include "route_hero1.c"

static int score_above(int b) {
    int s = 0;
    for (int x = b + 1; x < 256; x++) s += solved[x];
    return s;
}

static int protected_ok(const int *p, int np) {
    for (int i = 0; i < np; i++) if (!solved[p[i]]) return 0;
    return 1;
}

static void mark_phase_fixed(void) {
    memset(fixedmask, 0, sizeof(fixedmask));
    for (int a = 0; a < PROLEN; a++) fixedmask[a] = 1;
    /* Exact first-pass-equivalence chain found by prologue_phase_synth.c. */
    fixedmask[40] = fixedmask[42] = fixedmask[62] = 1;
    fixedmask[71] = fixedmask[72] = fixedmask[73] = fixedmask[123] = 1;
    fixedmask[N - 2] = fixedmask[N - 1] = 1;
}

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "low-phase-desc.mal";
    int passes = 4, lo_block = 4, ownspan = 9, steps = 220, witcap = 512;
    int protected_inputs[16], nprotected = 0, order = 0, verbose = 0;
    int fix121 = 0;
    int extra_fixed[32], nextra_fixed = 0;
    long nodes = 3000000000L;
    N = 3451; PROLEN = 34;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-prolen") && i + 1 < argc) PROLEN = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-passes") && i + 1 < argc) passes = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-lo") && i + 1 < argc) lo_block = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-span") && i + 1 < argc) ownspan = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-steps") && i + 1 < argc) steps = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-wit") && i + 1 <argc) witcap = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-nodes") && i + 1 < argc) nodes = atol(argv[++i]);
        else if (!strcmp(argv[i], "-order") && i + 1 < argc) order = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-protect") && i + 1 < argc && nprotected < 16)
            protected_inputs[nprotected++] = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-verbose")) verbose = 1;
        else if (!strcmp(argv[i], "-fix121")) fix121 = 1;
        else if (!strcmp(argv[i], "-fix") && i + 1 < argc && nextra_fixed < 32)
            extra_fixed[nextra_fixed++] = atoi(argv[++i]);
        else return 2;
    }
    if (!seed || ownspan > RMAXCELL || witcap < 1 || lo_block < 4) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];

    FILE *f = fopen(seed, "rb");
    if (!f) { perror(seed); return 2; }
    int got = (int)fread(prog, 1, M, f); fclose(f);
    if (got != N) { fprintf(stderr, "seed length %d != N %d\n", got, N); return 2; }
    mark_phase_fixed(); if (fix121) fixedmask[121] = 1;
    for (int i = 0; i < nextra_fixed; i++)
        if (extra_fixed[i] >= 0 && extra_fixed[i] < N) fixedmask[extra_fixed[i]] = 1;
    rebuild_all(); full_resim();
    fprintf(stderr, "desc start %d/256 misses:", cur_score); misses(); fputc('\n', stderr);
    if (!protected_ok(protected_inputs, nprotected)) {
        fprintf(stderr, "cannot semantically protect an unsolved input\n");
        return 2;
    }

    static uint8_t global_best[M]; memcpy(global_best, prog, N);
    int best = cur_score;
    rorder = order; rstepcap = steps; rnodecap = nodes;
    for (int pass = 0; pass < passes; pass++) {
        int pass_start = cur_score, repaired = 0, infeasible = 0;
        for (int b = 255; b >= lo_block; b--) {
            if (solved[b]) continue;
            if (verbose) fprintf(stderr, "try b=%d score=%d\n", b, cur_score);
            int cells[RMAXCELL], nc = 0;
            for (int a = 9 * b + 1; a <= 9 * b + ownspan && a < N; a++)
                if (!is_fixed(a)) cells[nc++] = a;
            if (!nc) { infeasible++; continue; }
            int found = rsolve(b, cells, nc);
            full_resim();
            if (!found) { infeasible++; continue; }

            int above0 = score_above(b), base0 = cur_score;
            int tries = found < witcap ? found : witcap;
            int best_w = -1, best_delta = -9999, best_changes = 9999;
            for (int s = 0; s < tries; s++) {
                uint8_t save[RMAXCELL]; int changed = 0;
                for (int i = 0; i < rn[s]; i++) {
                    save[i] = prog[raddr[s][i]];
                    changed += save[i] != rbyte[s][i];
                }
                apply_changes(raddr[s], rbyte[s], rn[s]);
                /* Incremental rescoring is exact for a forward edit, but a
                 * rollback can make a case resume touching a changed cell
                 * that its speculative trace no longer contained.  Full
                 * rescoring on both sides keeps witness comparison exact. */
                full_resim();
                int admissible = solved[b] && score_above(b) >= above0 &&
                                 protected_ok(protected_inputs, nprotected);
                int delta = admissible ? cur_score - base0 : -9999;
                apply_changes(raddr[s], save, rn[s]);
                full_resim();
                if (delta > best_delta || (delta == best_delta && changed < best_changes)) {
                    best_delta = delta; best_changes = changed; best_w = s;
                }
            }
            if (best_w >= 0 && best_delta > -9999) {
                apply_changes(raddr[best_w], rbyte[best_w], rn[best_w]);
                full_resim();
                repaired++;
                if (cur_score > best) {
                    best = cur_score; memcpy(global_best, prog, N); write_prog(out);
                    fprintf(stderr, "BEST %d/256 pass=%d b=%d witness=%d delta=%d misses:",
                            best, pass + 1, b, best_w, best_delta);
                    misses(); fputc('\n', stderr);
                }
            }
        }
        fprintf(stderr, "pass %d: %d -> %d repaired=%d infeasible=%d misses:",
                pass + 1, pass_start, cur_score, repaired, infeasible);
        misses(); fputc('\n', stderr);
        if (cur_score == pass_start && pass > 0) break;
    }
    memcpy(prog, global_best, N); rebuild_all(); full_resim(); write_prog(out);
    fprintf(stderr, "desc final %d/256 misses:", cur_score); misses(); fputc('\n', stderr);
    return 0;
}
