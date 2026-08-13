/* Exhaustively scan program lengths and legal final-byte pairs while keeping
 * the hero1 2305-byte tape as a prefix.  This intentionally includes hero1's
 * original-prologue simulator; the hero3 closed-form state is not equivalent. */
#define main hero1_main
#include "../xor-1-len4096-hero1/hero.c"
#undef main

static uint8_t seedbuf[M];
static int seedlen;

static void init_quiet(void) {
    for (int a = 0; a < PROLEN; a++) prog[a] = (uint8_t)PROLOGUE[a];
    prog[32] = (uint8_t)byte_for(JMP, 32);
    for (int a = PROLEN; a < N; a++) prog[a] = (uint8_t)byte_for(NOP, a);
    for (int i = 0; i < 6; i++)
        if (forced_addr[i] < N) prog[forced_addr[i]] = (uint8_t)forced_val[i];
    for (int a = PROLEN; a < seedlen && a < N; a++)
        if (!is_fixed(a)) prog[a] = seedbuf[a];
}

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "hero1-length-best.mal";
    int nlo = 2305, nhi = 4096, shard = 0, nshards = 1;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-lo") && i + 1 < argc) nlo = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-hi") && i + 1 < argc) nhi = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-shard") && i + 1 < argc) {
            if (sscanf(argv[++i], "%d/%d", &shard, &nshards) != 2) return 2;
        } else return 2;
    }
    if (!seed || nlo < 2305 || nhi > 4096 || nlo > nhi ||
        shard < 0 || shard >= nshards) return 2;

    FILE *f = fopen(seed, "rb");
    if (!f) return 2;
    seedlen = (int)fread(seedbuf, 1, M, f);
    fclose(f);
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed();

    int best = -1, best_n = -1, best_k1 = -1, best_k2 = -1;
    static uint8_t bestprog[M];
    for (N = nlo; N <= nhi; N++) {
        if ((N - nlo) % nshards != shard) continue;
        init_quiet();
        for (int k1 = 0; k1 < 8; k1++) for (int k2 = 0; k2 < 8; k2++) {
            prog[N - 2] = (uint8_t)byte_for(CODES[k1], N - 2);
            prog[N - 1] = (uint8_t)byte_for(CODES[k2], N - 1);
            rebuild_all();
            full_resim();
            if (cur_score > best) {
                best = cur_score;
                best_n = N;
                best_k1 = k1;
                best_k2 = k2;
                memcpy(bestprog, prog, N);
                write_prog(out);
                fprintf(stderr, "BEST shard=%d/%d score=%d N=%d pair=%d/%d misses:",
                        shard, nshards, best, N, CODES[k1], CODES[k2]);
                for (int b = 0; b < 256; b++)
                    if (!solved[b]) fprintf(stderr, " %d", b);
                fputc('\n', stderr);
            }
        }
    }
    N = best_n;
    memcpy(prog, bestprog, N);
    rebuild_all();
    full_resim();
    write_prog(out);
    fprintf(stderr, "FINAL shard=%d/%d score=%d N=%d pair=%d/%d misses:",
            shard, nshards, best, N, CODES[best_k1], CODES[best_k2]);
    for (int b = 0; b < 256; b++)
        if (!solved[b]) fprintf(stderr, " %d", b);
    fputc('\n', stderr);
    return 0;
}
