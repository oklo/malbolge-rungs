/* Exhaustive legal one-cell neighborhood of a hero1 candidate. */
#define main hero1_main
#include "../xor-1-len4096-hero1/hero.c"
#undef main

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "single-best.mal";
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
    static uint8_t bestprog[M]; memcpy(bestprog, prog, N);
    int baseline = cur_score, best = -1, best_a = -1, best_v = -1, nsolve = 0;
    for (int a = PROLEN; a < N; a++) {
        int ad[1] = {a}; uint8_t old[1] = {prog[a]};
        for (int k = 0; k < 8; k++) {
            uint8_t v[1] = {(uint8_t)byte_for(CODES[k], a)};
            if (v[0] == old[0]) continue;
            apply_changes(ad, v, 1);
            int protected_ok = 1;
            for (int p = 0; p < nprotected; p++) protected_ok &= solved[protected_inputs[p]];
            if (solved[target] && protected_ok) {
                nsolve++;
                if (cur_score > best) {
                    best = cur_score; best_a = a; best_v = v[0];
                    memcpy(bestprog, prog, N);
                    fprintf(stderr, "BEST target=%d score=%d/256 a=%d v=%d misses:",
                            target, best, a, v[0]);
                    for (int b = 0; b < 256; b++) if (!solved[b]) fprintf(stderr, " %d", b);
                    fputc('\n', stderr);
                }
            }
            apply_changes(ad, old, 1);
        }
    }
    fprintf(stderr, "baseline=%d target=%d solving mutations=%d best=%d a=%d v=%d\n",
            baseline, target, nsolve, best, best_a, best_v);
    if (best >= 0) { memcpy(prog, bestprog, N); rebuild_all(); full_resim(); write_prog(out); }
    return best < 0;
}
