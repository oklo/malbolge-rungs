/* Cross an alternative own-block route for one fragile low input with the
 * complete own-block witness families for inputs 8 and 9.  Required initial
 * bytes from each execution trace turn the three searches into an exact
 * compatibility problem over the only region any family can modify. */
#define RMAXSOL 65536
#define ROUTE_HERO1_NO_MAIN
#include "route_hero1.c"

#define WLO 33
#define WHI 128
#define W (WHI - WLO + 1)

typedef struct {
    uint8_t value[W];
    int witness;
} Signature;

static Signature sigx[RMAXSOL], sig8[RMAXSOL], sig9[RMAXSOL];

typedef struct { uint64_t hash; int index; } HashIndex;
static HashIndex hindex[RMAXSOL];

static int hash_index_cmp(const void *av, const void *bv) {
    const HashIndex *a = av, *b = bv;
    return a->hash < b->hash ? -1 : a->hash > b->hash;
}

static uint64_t signature_hash(const Signature *s, const int *pos, int npos) {
    uint64_t h = UINT64_C(1469598103934665603);
    for (int i = 0; i < npos; i++) {
        h ^= (uint64_t)s->value[pos[i]];
        h *= UINT64_C(1099511628211);
    }
    return h;
}

static int compatible(const Signature *a, const Signature *b) {
    for (int i = 0; i < W; i++)
        if (a->value[i] && b->value[i] && a->value[i] != b->value[i]) return 0;
    return 1;
}

static void merge(Signature *dst, const Signature *a, const Signature *b) {
    for (int i = 0; i < W; i++) dst->value[i] = a->value[i] ? a->value[i] : b->value[i];
}

static int gather(int b, int order, int steps, long nodes, int wide, Signature *out) {
    int cells[RMAXCELL], nc = 0;
    int lo = wide ? WLO : 9 * b + 1;
    int hi = wide ? WHI : 9 * b + 9;
    for (int a = lo; a <= hi; a++)
        if (!is_fixed(a)) cells[nc++] = a;
    rorder = order; rstepcap = steps; rnodecap = nodes;
    int found = rsolve(b, cells, nc), nout = 0;
    fprintf(stderr, "b=%d witnesses=%d nodes=%ld%s cells=%d\n",
            b, found, rnodes, rnodes > rnodecap ? " capped" : "", nc);

    static uint8_t base[M]; memcpy(base, prog, N);
    for (int s = 0; s < found && nout < RMAXSOL; s++) {
        Signature q = {.witness = s};
        memcpy(prog, base, N);
        for (int i = 0; i < rn[s]; i++) prog[raddr[s][i]] = rbyte[s][i];
        rebuild_all();
        rec_touch = 1; int ok = simulate(b); rec_touch = 0;
        if (!ok) continue;
        for (int i = 0; i < rn[s]; i++) {
            int a = raddr[s][i];
            if (a >= WLO && a <= WHI) q.value[a - WLO] = rbyte[s][i];
        }
        for (int i = 0; i < ntl; i++) {
            int a = tl[i];
            if (a >= WLO && a <= WHI && !q.value[a - WLO])
                q.value[a - WLO] = prog[a];
        }
        out[nout++] = q;
    }
    memcpy(prog, base, N); rebuild_all(); full_resim();
    fprintf(stderr, "b=%d signatures=%d\n", b, nout);
    return nout;
}

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "hero1-joint-low.mal";
    int extra = -1, orderx = 0, order8 = 0, order9 = 0, steps = 100, require = -1;
    int wide_extra = 0, pairs_only = 0;
    long nodes = 3000000000L;
    N = 2605;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-extra") && i + 1 < argc) extra = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-orderx") && i + 1 < argc) orderx = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-order8") && i + 1 < argc) order8 = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-order9") && i + 1 < argc) order9 = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-steps") && i + 1 < argc) steps = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-nodes") && i + 1 < argc) nodes = atol(argv[++i]);
        else if (!strcmp(argv[i], "-require") && i + 1 < argc) require = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-wide-extra")) wide_extra = 1;
        else if (!strcmp(argv[i], "-pairs-only")) pairs_only = 1;
        else return 2;
    }
    if (!seed || extra < 0 || extra > 255) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); init_prog(seed); rebuild_all(); full_resim();
    static uint8_t base[M], bestprog[M];
    memcpy(base, prog, N); memcpy(bestprog, prog, N);
    int baseline = cur_score, best = -1, best_low = -1, best_changes = 9999;
    int nx = gather(extra, orderx, steps, nodes, wide_extra, sigx);
    int n8 = gather(8, order8, steps, nodes, 0, sig8);
    int n9 = gather(9, order9, steps, nodes, 0, sig9);

    unsigned long long pairs = 0, triples = 0, valid = 0;
    int bi = -1, bj = -1, bk = -1;
    Signature p89;
    if (pairs_only) {
        for (int i = 0; i < n8; i++) for (int j = 0; j < n9; j++)
            pairs += compatible(&sig8[i], &sig9[j]);
        fprintf(stderr, "joint-low extra=%d compatible-pairs=%llu\n", extra, pairs);
        return 0;
    }
    int keypos[W], nkey = 0;
    if (wide_extra) {
        for (int x = 0; x < W; x++) {
            int allx = 1, all8 = 1, all9 = 1;
            for (int k = 0; k < nx; k++) allx &= sigx[k].value[x] != 0;
            for (int i = 0; i < n8; i++) all8 &= sig8[i].value[x] != 0;
            for (int j = 0; j < n9; j++) all9 &= sig9[j].value[x] != 0;
            if (allx && (all8 || all9)) keypos[nkey++] = x;
        }
        for (int k = 0; k < nx; k++) {
            hindex[k].hash = signature_hash(&sigx[k], keypos, nkey);
            hindex[k].index = k;
        }
        qsort(hindex, nx, sizeof(*hindex), hash_index_cmp);
        fprintf(stderr, "compatibility hash uses %d universal cells\n", nkey);
    }
    for (int i = 0; i < n8; i++) for (int j = 0; j < n9; j++) {
        if (!compatible(&sig8[i], &sig9[j])) continue;
        pairs++; merge(&p89, &sig8[i], &sig9[j]);
        int begin = 0, end = nx;
        if (wide_extra && nkey) {
            uint64_t h = signature_hash(&p89, keypos, nkey);
            int lo = 0, hi = nx;
            while (lo < hi) { int m = lo + (hi - lo) / 2;
                if (hindex[m].hash < h) lo = m + 1; else hi = m; }
            begin = lo; hi = nx;
            while (lo < hi) { int m = lo + (hi - lo) / 2;
                if (hindex[m].hash <= h) lo = m + 1; else hi = m; }
            end = lo;
        }
        for (int q = begin; q < end; q++) {
            int k = wide_extra && nkey ? hindex[q].index : q;
            if (!compatible(&p89, &sigx[k])) continue;
            triples++;
            memcpy(prog, base, N);
            int changed = 0;
            for (int x = 0; x < W; x++) {
                uint8_t v = p89.value[x] ? p89.value[x] : sigx[k].value[x];
                if (v) { changed += prog[WLO + x] != v; prog[WLO + x] = v; }
            }
            rebuild_all(); full_resim();
            if (!solved[extra] || !solved[8] || !solved[9]) continue;
            if (require >= 0 && (require > 255 || !solved[require])) continue;
            valid++;
            int low = 0; for (int b = 0; b <= 17; b++) low += solved[b];
            if (low > best_low || (low == best_low &&
                (cur_score > best || (cur_score == best && changed < best_changes)))) {
                best = cur_score; best_low = low; best_changes = changed;
                bi = i; bj = j; bk = k;
                memcpy(bestprog, prog, N); write_prog(out);
                fprintf(stderr, "BEST extra=%d raw=%d low=%d/18 sig=%d,%d,%d wit=%d,%d,%d changed=%d misses:",
                        extra, best, best_low, i, j, k, sig8[i].witness,
                        sig9[j].witness, sigx[k].witness, changed);
                misses(); fputc('\n', stderr);
            }
        }
    }
    memcpy(prog, bestprog, N); rebuild_all(); full_resim();
    if (valid) write_prog(out);
    fprintf(stderr, "joint-low extra=%d final=%d low=%d/18 sig=%d,%d,%d pairs=%llu triples=%llu valid=%llu misses:",
            extra, cur_score, best_low, bi, bj, bk, pairs, triples, valid);
    misses(); fputc('\n', stderr);
    return best > baseline ? 0 : 1;
}
