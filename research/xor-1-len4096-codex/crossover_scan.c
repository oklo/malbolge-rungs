/* Exhaustively score every recombination of the cells on which two nearby
 * hero1 tapes differ.  Intended for independently reconstructed basins. */
#define main hero1_main
#include "../xor-1-len4096-hero1/hero.c"
#undef main

int main(int argc, char **argv) {
    const char *a_path = NULL, *b_path = NULL, *out = "crossover-best.mal";
    int start_bit = 0, shard_bits = -1;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-a") && i + 1 < argc) a_path = argv[++i];
        else if (!strcmp(argv[i], "-b") && i + 1 < argc) b_path = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-slice") && i + 1 < argc) {
            if (sscanf(argv[++i], "%d:%d", &start_bit, &shard_bits) != 2) return 2;
        }
        else return 2;
    }
    if (!a_path || !b_path) return 2;
    static uint8_t a[M], b[M], bestprog[M];
    FILE *fa = fopen(a_path, "rb"), *fb = fopen(b_path, "rb");
    if (!fa || !fb) return 2;
    int na = (int)fread(a, 1, M, fa), nb = (int)fread(b, 1, M, fb);
    fclose(fa); fclose(fb); if (na != nb) return 2; N = na;
    int diff[64], nd = 0;
    for (int i = 0; i < N; i++) if (a[i] != b[i]) {
        if (nd == 64) return 2; diff[nd++] = i;
    }
    if (shard_bits < 0) shard_bits = nd;
    if (nd > 64 || start_bit < 0 || shard_bits < 0 || start_bit + shard_bits > nd || shard_bits > 24) {
        fprintf(stderr, "unsupported differences/slice: %d %d:%d\n", nd, start_bit, shard_bits); return 2;
    }
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); int best = -1; unsigned long long bestmask = 0;
    unsigned long long total = 1ULL << shard_bits;
    for (unsigned long long local = 0; local < total; local++) {
        unsigned long long mask = local << start_bit;
        memcpy(prog, a, N);
        for (int j = 0; j < nd; j++) if (mask & (1ULL << j)) prog[diff[j]] = b[diff[j]];
        rebuild_all(); full_resim();
        if (cur_score > best) {
            best = cur_score; bestmask = mask; memcpy(bestprog, prog, N);
            fprintf(stderr, "BEST %d/256 mask=%llx misses:", best, mask);
            for (int x = 0; x < 256; x++) if (!solved[x]) fprintf(stderr, " %d", x);
            fputc('\n', stderr);
        }
    }
    memcpy(prog, bestprog, N); rebuild_all(); full_resim(); write_prog(out);
    fprintf(stderr, "final=%d/256 differences=%d slice=%d:%d combinations=%llu mask=%llx\n",
            best, nd, start_bit, shard_bits, total, bestmask);
    return 0;
}
