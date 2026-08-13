/* Exhaustive legal two-cell neighborhood sufficient for a currently failing
 * input: at least one effective change must touch that input's baseline trace. */
#define main hero1_main
#include "../xor-1-len4096-hero1/hero.c"
#undef main

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "pair-best.mal";
    int target = 1, protected_inputs[16], nprotected = 0; N = 2605;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-target") && i + 1 < argc) target = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-protect") && i + 1 < argc && nprotected < 16)
            protected_inputs[nprotected++] = atoi(argv[++i]);
        else return 2;
    }
    if (!seed || target < 0 || target > 255) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); init_prog(seed); rebuild_all(); full_resim();
    rec_touch = 1; (void)simulate(target); rec_touch = 0;
    int first[128], nf = 0;
    for (int i = 0; i < ntl; i++) {
        int a = tl[i], seen = 0;
        if (a < PROLEN || a >= N) continue;
        for (int j = 0; j < nf; j++) seen |= first[j] == a;
        if (!seen) first[nf++] = a;
    }
    static uint8_t bestprog[M];
    int best = -1, best_a = -1, best_b = -1, best_va = -1, best_vb = -1;
    unsigned long long tested = 0, nsolve = 0;
    for (int fi = 0; fi < nf; fi++) {
        int a = first[fi], aa[1] = {a}; uint8_t oa[1] = {prog[a]};
        for (int ka = 0; ka < 8; ka++) {
            uint8_t va[1] = {(uint8_t)byte_for(CODES[ka], a)};
            if (va[0] == oa[0]) continue;
            apply_changes(aa, va, 1);
            for (int b = PROLEN; b < N; b++) if (b != a) {
                int ab[1] = {b}; uint8_t ob[1] = {prog[b]};
                for (int kb = 0; kb < 8; kb++) {
                    uint8_t vb[1] = {(uint8_t)byte_for(CODES[kb], b)};
                    if (vb[0] == ob[0]) continue;
                    tested++; apply_changes(ab, vb, 1);
                    int protected_ok = 1;
                    for (int p = 0; p < nprotected; p++) protected_ok &= solved[protected_inputs[p]];
                    if (solved[target] && protected_ok) {
                        nsolve++;
                        if (cur_score > best) {
                            best = cur_score; best_a = a; best_va = va[0];
                            best_b = b; best_vb = vb[0]; memcpy(bestprog, prog, N);
                            fprintf(stderr, "BEST target=%d score=%d/256 %d=%d %d=%d misses:",
                                    target, best, a, va[0], b, vb[0]);
                            for (int x = 0; x < 256; x++) if (!solved[x]) fprintf(stderr, " %d", x);
                            fputc('\n', stderr);
                        }
                    }
                    apply_changes(ab, ob, 1);
                }
            }
            apply_changes(aa, oa, 1);
        }
    }
    fprintf(stderr, "target=%d trace-cells=%d tested=%llu solves=%llu best=%d %d=%d %d=%d\n",
            target, nf, tested, nsolve, best, best_a, best_va, best_b, best_vb);
    if (best >= 0) { memcpy(prog, bestprog, N); rebuild_all(); full_resim(); write_prog(out); }
    return best < 0;
}
