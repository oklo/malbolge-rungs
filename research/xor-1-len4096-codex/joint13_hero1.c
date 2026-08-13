/* Cross wide exact route families for the two reachable champion failures,
 * inputs 1 and 3.  Trace signatures encode every initial low-window byte each
 * route requires, turning compatible executions into a hash join. */
#define RMAXSOL 65536
#define ROUTE_HERO1_NO_MAIN
#include "route_hero1.c"

#define WLO 33
#define WHI 128
#define W (WHI - WLO + 1)

typedef struct { uint8_t value[W]; int witness; } Signature;
typedef struct { uint64_t hash; int index; } HashIndex;
static Signature sig1[RMAXSOL], sig3[RMAXSOL];
static HashIndex hindex[RMAXSOL];

static int hcmp(const void *av, const void *bv) {
    const HashIndex *a = av, *b = bv;
    return a->hash < b->hash ? -1 : a->hash > b->hash;
}
static uint64_t sighash(const Signature *s, const int *pos, int n) {
    uint64_t h = UINT64_C(1469598103934665603);
    for (int i = 0; i < n; i++) { h ^= s->value[pos[i]]; h *= UINT64_C(1099511628211); }
    return h;
}
static int compatible(const Signature *a, const Signature *b) {
    for (int x = 0; x < W; x++)
        if (a->value[x] && b->value[x] && a->value[x] != b->value[x]) return 0;
    return 1;
}
static int gather(int b, int order, int steps, long nodes, Signature *out) {
    int cells[RMAXCELL], nc = 0;
    for (int a = WLO; a <= WHI; a++) if (!is_fixed(a)) cells[nc++] = a;
    rorder = order; rstepcap = steps; rnodecap = nodes;
    int found = rsolve(b, cells, nc), nout = 0;
    fprintf(stderr, "b=%d order=%d witnesses=%d nodes=%ld%s cells=%d\n",
            b, order, found, rnodes, rnodes > rnodecap ? " capped" : "", nc);
    static uint8_t base[M]; memcpy(base, prog, N);
    for (int s = 0; s < found && nout < RMAXSOL; s++) {
        Signature q = {.witness = s};
        /* Every mutable cell is far from the two tail seeds.  The simulator
         * unwinds its own writes, so patch and restore only witness cells;
         * rebuilding all 59,049 words for every signature is unnecessary. */
        for (int i = 0; i < rn[s]; i++) {
            prog[raddr[s][i]] = rbyte[s][i];
            mem[raddr[s][i]] = rbyte[s][i];
        }
        rec_touch = 1; int ok = simulate(b); rec_touch = 0;
        if (!ok) {
            for (int i = 0; i < rn[s]; i++) {
                prog[raddr[s][i]] = base[raddr[s][i]];
                mem[raddr[s][i]] = base[raddr[s][i]];
            }
            continue;
        }
        for (int i = 0; i < rn[s]; i++) {
            int a = raddr[s][i];
            if (a >= WLO && a <= WHI) q.value[a - WLO] = rbyte[s][i];
        }
        for (int i = 0; i < ntl; i++) {
            int a = tl[i];
            if (a >= WLO && a <= WHI && !q.value[a - WLO]) q.value[a - WLO] = prog[a];
        }
        out[nout++] = q;
        for (int i = 0; i < rn[s]; i++) {
            prog[raddr[s][i]] = base[raddr[s][i]];
            mem[raddr[s][i]] = base[raddr[s][i]];
        }
    }
    memcpy(prog, base, N); rebuild_all(); full_resim();
    fprintf(stderr, "b=%d signatures=%d\n", b, nout);
    return nout;
}

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "hero1-joint13.mal";
    int order1 = 0, order3 = 0, steps = 220;
    int input_a = 1, input_b = 3;
    long nodes = 3000000000L, pair_cap = 200000000L;
    N = 2605;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-order1") && i + 1 < argc) order1 = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-order3") && i + 1 < argc) order3 = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-a") && i + 1 < argc) input_a = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-b") && i + 1 < argc) input_b = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-steps") && i + 1 < argc) steps = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-nodes") && i + 1 < argc) nodes = atol(argv[++i]);
        else if (!strcmp(argv[i], "-pair-cap") && i + 1 < argc) pair_cap = atol(argv[++i]);
        else return 2;
    }
    if (!seed) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); init_prog(seed); rebuild_all(); full_resim();
    static uint8_t base[M], bestprog[M];
    memcpy(base, prog, N); memcpy(bestprog, prog, N);
    int baseline = cur_score, best = -1, best_changes = 9999, bi = -1, bj = -1;
    int n1 = gather(input_a, order1, steps, nodes, sig1);
    int n3 = gather(input_b, order3, steps, nodes, sig3);

    int keypos[W], nkey = 0;
    for (int x = 0; x < W; x++) {
        int all1 = n1 > 0, all3 = n3 > 0;
        for (int i = 0; i < n1; i++) all1 &= sig1[i].value[x] != 0;
        for (int j = 0; j < n3; j++) all3 &= sig3[j].value[x] != 0;
        if (all1 && all3) keypos[nkey++] = x;
    }
    fprintf(stderr, "joint13 hash uses %d universal cells\n", nkey);
    if (!nkey) return 2;
    for (int i = 0; i < n1; i++) {
        hindex[i].hash = sighash(&sig1[i], keypos, nkey); hindex[i].index = i;
    }
    qsort(hindex, n1, sizeof(*hindex), hcmp);

    unsigned long long checked = 0, compatible_pairs = 0, valid = 0;
    int capped = 0;
    for (int j = 0; j < n3 && !capped; j++) {
        uint64_t h = sighash(&sig3[j], keypos, nkey);
        int lo = 0, hi = n1;
        while (lo < hi) { int m = lo + (hi - lo) / 2;
            if (hindex[m].hash < h) lo = m + 1; else hi = m; }
        int begin = lo; hi = n1;
        while (lo < hi) { int m = lo + (hi - lo) / 2;
            if (hindex[m].hash <= h) lo = m + 1; else hi = m; }
        int end = lo;
        for (int q = begin; q < end; q++) {
            if (++checked > (unsigned long long)pair_cap) { capped = 1; break; }
            int i = hindex[q].index;
            if (!compatible(&sig1[i], &sig3[j])) continue;
            compatible_pairs++;
            memcpy(prog, base, N); int changed = 0;
            for (int x = 0; x < W; x++) {
                uint8_t v = sig1[i].value[x] ? sig1[i].value[x] : sig3[j].value[x];
                if (v) { changed += prog[WLO + x] != v; prog[WLO + x] = v; }
            }
            rebuild_all(); full_resim();
            if (!solved[input_a] || !solved[input_b]) continue;
            valid++;
            if (cur_score > best || (cur_score == best && changed < best_changes)) {
                best = cur_score; best_changes = changed; bi = i; bj = j;
                memcpy(bestprog, prog, N); write_prog(out);
                fprintf(stderr, "BEST joint(%d,%d) raw=%d sig=%d,%d wit=%d,%d changed=%d misses:",
                        input_a, input_b, best, i, j, sig1[i].witness, sig3[j].witness, changed);
                misses(); fputc('\n', stderr);
            }
        }
    }
    memcpy(prog, bestprog, N); rebuild_all(); full_resim();
    if (valid) write_prog(out);
    fprintf(stderr, "joint13 final=%d sig=%d,%d changed=%d checked=%llu compatible=%llu valid=%llu%s misses:",
            cur_score, bi, bj, best_changes, checked, compatible_pairs, valid,
            capped ? " pair-capped" : "");
    misses(); fputc('\n', stderr);
    return best > baseline ? 0 : 1;
}
