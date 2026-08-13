/* Enumerate exact own-block witnesses for hero1 inputs 8 and 9, convert each
 * execution into a required-byte signature over the shared window, and cross
 * the signatures.  Unlike sequential repair, this keeps paths that coexist
 * even when one input executes cells owned by the other. */
#define RMAXSOL 65536
#define ROUTE_HERO1_NO_MAIN
#include "route_hero1.c"

#define JLO 73
#define JHI 120
#define JW (JHI - JLO + 1)

typedef struct {
    uint8_t value[JW];
    int witness;
} Signature;

static Signature sig8[RMAXSOL], sig9[RMAXSOL];
static int nsig8, nsig9;

static int compatible(const Signature *a, const Signature *b) {
    for (int i = 0; i < JW; i++)
        if (a->value[i] && b->value[i] && a->value[i] != b->value[i]) return 0;
    return 1;
}

static int duplicate(const Signature *s, const Signature *set, int n) {
    for (int i = 0; i < n; i++)
        if (!memcmp(s->value, set[i].value, JW)) return 1;
    return 0;
}

static int gather(int b, int order, int steps, long nodes,
                  Signature *out, int *nout) {
    int cells[RMAXCELL], nc = 0;
    for (int a = 9 * b + 1; a <= 9 * b + 9; a++)
        if (!is_fixed(a)) cells[nc++] = a;
    rorder = order; rstepcap = steps; rnodecap = nodes;
    int found = rsolve(b, cells, nc);
    fprintf(stderr, "b=%d order=%d witnesses=%d nodes=%ld%s cells=%d\n",
            b, order, found, rnodes, rnodes > rnodecap ? " capped" : "", nc);

    static uint8_t base[M]; memcpy(base, prog, N);
    for (int s = 0; s < found; s++) {
        Signature q = {.witness = s};
        memcpy(prog, base, N);
        for (int i = 0; i < rn[s]; i++) prog[raddr[s][i]] = rbyte[s][i];
        rebuild_all(); full_resim();
        if (!solved[b]) continue;

        for (int i = 0; i < rn[s]; i++) {
            int a = raddr[s][i];
            if (a >= JLO && a <= JHI) q.value[a - JLO] = rbyte[s][i];
        }
        rec_touch = 1; (void)simulate(b); rec_touch = 0;
        for (int i = 0; i < ntl; i++) {
            int a = tl[i];
            if (a >= JLO && a <= JHI && !q.value[a - JLO])
                q.value[a - JLO] = prog[a];
        }
        /* The first 8,192 witnesses in every branch order had distinct
         * signatures.  Avoid a quadratic duplicate scan at the larger cap;
         * duplicate signatures are harmless in the compatibility crossing. */
        if (*nout < RMAXSOL) out[(*nout)++] = q;
    }
    memcpy(prog, base, N); rebuild_all(); full_resim();
    fprintf(stderr, "b=%d order=%d unique signatures=%d\n", b, order, *nout);
    return found;
}

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "hero1-joint89.mal", *pool_prefix = NULL;
    int order8 = 0, order9 = 0, steps = 100, objective_low = 0, require = -1;
    long nodes = 3000000000L;
    N = 2605;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-order8") && i + 1 < argc) order8 = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-order9") && i + 1 < argc) order9 = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-steps") && i + 1 < argc) steps = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-nodes") && i + 1 < argc) nodes = atol(argv[++i]);
        else if (!strcmp(argv[i], "-objective-low")) objective_low = 1;
        else if (!strcmp(argv[i], "-require") && i + 1 < argc) require = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-pool-prefix") && i + 1 < argc) pool_prefix = argv[++i];
        else return 2;
    }
    if (!seed) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); init_prog(seed); rebuild_all(); full_resim();
    static uint8_t base[M], bestprog[M];
    memcpy(base, prog, N); memcpy(bestprog, prog, N);
    int baseline = cur_score, best = -1;
    fprintf(stderr, "joint89 start %d/256 misses:", baseline); misses(); fputc('\n', stderr);

    gather(8, order8, steps, nodes, sig8, &nsig8);
    gather(9, order9, steps, nodes, sig9, &nsig9);

    unsigned long long pairs = 0, valid = 0;
    int best_i = -1, best_j = -1, best_changes = 9999, best_low = -1;
    static int pool_score[1 << 18], pool_i[1 << 18], pool_j[1 << 18], pool_changes[1 << 18];
    if (pool_prefix) {
        for (int m = 0; m < (1 << 18); m++) pool_score[m] = pool_i[m] = pool_j[m] = -1;
    }
    for (int i = 0; i < nsig8; i++) for (int j = 0; j < nsig9; j++) {
        if (!compatible(&sig8[i], &sig9[j])) continue;
        pairs++;
        memcpy(prog, base, N);
        int changed = 0;
        for (int x = 0; x < JW; x++) {
            uint8_t v = sig8[i].value[x] ? sig8[i].value[x] : sig9[j].value[x];
            if (v) {
                changed += prog[JLO + x] != v;
                prog[JLO + x] = v;
            }
        }
        rebuild_all(); full_resim();
        if (!solved[8] || !solved[9]) continue;
        if (require >= 0 && (require > 255 || !solved[require])) continue;
        valid++;
        int low_score = 0;
        unsigned low_mask = 0;
        for (int b = 0; b <= 17; b++) {
            low_score += solved[b];
            if (solved[b]) low_mask |= 1u << b;
        }
        if (pool_prefix && (cur_score > pool_score[low_mask] ||
            (cur_score == pool_score[low_mask] && changed < pool_changes[low_mask]))) {
            pool_score[low_mask] = cur_score; pool_changes[low_mask] = changed;
            pool_i[low_mask] = i; pool_j[low_mask] = j;
        }
        int better = objective_low
            ? (low_score > best_low ||
               (low_score == best_low && (cur_score > best ||
                (cur_score == best && changed < best_changes))))
            : (cur_score > best || (cur_score == best && changed < best_changes));
        if (better) {
            best = cur_score; best_low = low_score;
            best_changes = changed; best_i = i; best_j = j;
            memcpy(bestprog, prog, N); write_prog(out);
            fprintf(stderr, "BEST joint raw=%d low=%d/18 pair=%d,%d witnesses=%d,%d changed=%d misses:",
                    best, best_low, i, j, sig8[i].witness, sig9[j].witness, changed);
            misses(); fputc('\n', stderr);
        }
    }
    memcpy(prog, bestprog, N); rebuild_all(); full_resim(); write_prog(out);
    fprintf(stderr, "joint89 final=%d low=%d/18 pair=%d,%d changed=%d compatible=%llu valid=%llu misses:",
            cur_score, best_low, best_i, best_j, best_changes, pairs, valid);
    misses(); fputc('\n', stderr);
    if (pool_prefix) {
        int nout = 0;
        char path[1024];
        for (unsigned m = 0; m < (1u << 18); m++) {
            if (__builtin_popcount(m) < best_low || pool_i[m] < 0) continue;
            memcpy(prog, base, N);
            int i = pool_i[m], j = pool_j[m];
            for (int x = 0; x < JW; x++) {
                uint8_t v = sig8[i].value[x] ? sig8[i].value[x] : sig9[j].value[x];
                if (v) prog[JLO + x] = v;
            }
            snprintf(path, sizeof(path), "%s-%05x.mal", pool_prefix, m);
            write_prog(path); nout++;
            fprintf(stderr, "POOL mask=%05x low=%d raw=%d pair=%d,%d changed=%d path=%s\n",
                    m, __builtin_popcount(m), pool_score[m], i, j, pool_changes[m], path);
        }
        fprintf(stderr, "POOL total=%d at low=%d\n", nout, best_low);
    }
    return best > baseline ? 0 : 1;
}
