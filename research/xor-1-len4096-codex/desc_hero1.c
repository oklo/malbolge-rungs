/* Descending reconstruction for hero1 tapes, using the corrected wide DFS
 * from route_hero1.c.  It can freeze selected low-input traces, then rebuild
 * blocks from high to low without sacrificing already-settled higher inputs. */
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

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "hero1-desc.mal";
    int passes = 4, lo_block = 10, ownspan = 9, steps = 120, witcap = 128;
    int protected_inputs[16], nprotected = 0, order = 0;
    int semantic_protect = 0, verbose = 0;
    long nodes = 500000000L;
    N = 2605;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-passes") && i + 1 < argc) passes = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-lo") && i + 1 < argc) lo_block = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-span") && i + 1 < argc) ownspan = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-steps") && i + 1 < argc) steps = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-wit") && i + 1 < argc) witcap = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-nodes") && i + 1 < argc) nodes = atol(argv[++i]);
        else if (!strcmp(argv[i], "-order") && i + 1 < argc) order = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-protect") && i + 1 < argc && nprotected < 16)
            protected_inputs[nprotected++] = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-semantic-protect")) semantic_protect = 1;
        else if (!strcmp(argv[i], "-verbose")) verbose = 1;
        else return 2;
    }
    if (!seed || ownspan > RMAXCELL || witcap < 1) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); init_prog(seed); rebuild_all(); full_resim();
    fprintf(stderr, "desc start %d/256 misses:", cur_score); misses(); fputc('\n', stderr);

    for (int pi = 0; pi < nprotected; pi++) {
        int b = protected_inputs[pi];
        rec_touch = 1; int ok = simulate(b); rec_touch = 0;
        if (!ok) { fprintf(stderr, "cannot protect unsolved input %d\n", b); return 2; }
        if (!semantic_protect)
            for (int i = 0; i < ntl; i++)
                if (tl[i] >= 0 && tl[i] < N) fixedmask[tl[i]] = 1;
    }
    fixedmask[N - 2] = fixedmask[N - 1] = 1;
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
            /* rsolve() unwinds its speculative VM writes, but wr() updates the
             * cached solved[] state as it explores.  Recompute that cache from
             * the restored program before deciding whether to skip this input
             * or score any returned witnesses. */
            full_resim();
            if (verbose) fprintf(stderr, "  witnesses=%d score=%d solved=%d\n",
                                 found, cur_score, solved[b]);
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
                int admissible = score_above(b) >= above0 && protected_ok(protected_inputs, nprotected);
                int delta = admissible ? cur_score - base0 : -9999;
                apply_changes(raddr[s], save, rn[s]);
                if (delta > best_delta || (delta == best_delta && changed < best_changes)) {
                    best_delta = delta; best_changes = changed; best_w = s;
                }
            }
            if (best_w >= 0 && best_delta > -9999) {
                apply_changes(raddr[best_w], rbyte[best_w], rn[best_w]);
                repaired++;
                if (cur_score > best) {
                    best = cur_score; memcpy(global_best, prog, N); write_prog(out);
                    fprintf(stderr, "BEST %d/256 pass=%d b=%d witness=%d delta=%d misses:",
                            best, pass + 1, b, best_w, best_delta); misses(); fputc('\n', stderr);
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
