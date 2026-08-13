/* Exhaustively find the best two-cell score improvement while preserving
 * semantic locks.  Completeness: one edit must touch the baseline trace of an
 * input whose result changes, so the first-cell set is the union of failures. */
#ifdef HERO2
#define main hero2_main
#include "../xor-1-len4096-hero2/hero9.c"
#else
#define main hero1_main
#include "../xor-1-len4096-hero1/hero.c"
#endif
#undef main

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "pair-improved.mal";
    int locks[16], nlocks = 0, shard = 0, nshards = 1; N = 2605;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-lock") && i + 1 < argc && nlocks < 16) locks[nlocks++] = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-shard") && i + 1 < argc) {
            if (sscanf(argv[++i], "%d/%d", &shard, &nshards) != 2) return 2;
        } else return 2;
    }
    if (!seed || shard < 0 || shard >= nshards) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); init_prog(seed); rebuild_all(); full_resim();
    for (int i = 0; i < nlocks; i++) if (!solved[locks[i]]) return 2;
    int baseline = cur_score, first[M], nf = 0; static uint8_t seen[M];
    for (int x = 0; x < 256; x++) if (!solved[x]) {
        rec_touch = 1; (void)simulate(x); rec_touch = 0;
        for (int i = 0; i < ntl; i++) {
            int a = tl[i]; if (a >= PROLEN && a < N && !seen[a]) { seen[a] = 1; first[nf++] = a; }
        }
    }
    static uint8_t bestprog[M]; memcpy(bestprog, prog, N);
    int best = baseline, ba = -1, bb = -1, bva = -1, bvb = -1;
    unsigned long long tested = 0;
    for (int fi = shard; fi < nf; fi += nshards) {
        int a = first[fi], aa[1] = {a}; uint8_t oa[1] = {prog[a]};
        for (int ka = 0; ka < 8; ka++) {
            uint8_t va[1] = {(uint8_t)byte_for(CODES[ka], a)}; if (va[0] == oa[0]) continue;
            apply_changes(aa, va, 1);
            for (int b = PROLEN; b < N; b++) if (b != a) {
                int ab[1] = {b}; uint8_t ob[1] = {prog[b]};
                for (int kb = 0; kb < 8; kb++) {
                    uint8_t vb[1] = {(uint8_t)byte_for(CODES[kb], b)}; if (vb[0] == ob[0]) continue;
                    tested++; apply_changes(ab, vb, 1);
                    int ok = 1; for (int p = 0; p < nlocks; p++) ok &= solved[locks[p]];
                    if (ok && cur_score > best) {
                        best = cur_score; ba = a; bva = va[0]; bb = b; bvb = vb[0];
                        memcpy(bestprog, prog, N); write_prog(out);
                        fprintf(stderr, "BEST %d/256 %d=%d %d=%d misses:", best, a, va[0], b, vb[0]);
                        for (int x = 0; x < 256; x++) if (!solved[x]) fprintf(stderr, " %d", x);
                        fputc('\n', stderr);
                    }
                    apply_changes(ab, ob, 1);
                }
            }
            apply_changes(aa, oa, 1);
        }
    }
    fprintf(stderr, "baseline=%d final=%d shard=%d/%d first=%d tested=%llu best=%d=%d %d=%d\n",
            baseline, best, shard, nshards, nf, tested, ba, bva, bb, bvb);
    if (best > baseline) { memcpy(prog, bestprog, N); rebuild_all(); full_resim(); write_prog(out); }
    return best <= baseline;
}
