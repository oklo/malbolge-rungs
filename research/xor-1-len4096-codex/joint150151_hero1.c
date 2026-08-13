/* Cross exact witnesses for the coupled hero1 inputs 150 and 151. */
#define ROUTE_HERO1_NO_MAIN
#include "route_hero1.c"

static void protect_trace(int b) {
    rec_touch = 1;
    int ok = simulate(b);
    rec_touch = 0;
    if (!ok) return;
    for (int i = 0; i < ntl; i++)
        if (tl[i] >= 0 && tl[i] < N) fixedmask[tl[i]] = 1;
}

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "hero1-joint150151.mal";
    int order1 = 0, order2 = 0, first_span = 12, second_span = 61;
    long nodes1 = 3000000000L, nodes2 = 50000000L;
    N = 2605;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-order1") && i + 1 < argc) order1 = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-order2") && i + 1 < argc) order2 = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-span1") && i + 1 < argc) first_span = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-span2") && i + 1 < argc) second_span = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-nodes1") && i + 1 < argc) nodes1 = atol(argv[++i]);
        else if (!strcmp(argv[i], "-nodes2") && i + 1 < argc) nodes2 = atol(argv[++i]);
        else return 2;
    }
    if (!seed || first_span > RMAXCELL || second_span > RMAXCELL) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); init_prog(seed); rebuild_all(); full_resim();
    static uint8_t original[M], bestprog[M];
    memcpy(original, prog, N); memcpy(bestprog, prog, N);
    int best = cur_score;
    static int f_n[RMAXSOL], f_a[RMAXSOL][RMAXCELL];
    static uint8_t f_b[RMAXSOL][RMAXCELL];
    const int force_ops[] = {JMP, ROT, MOVD, CRZ, NOP, HLT};

    for (unsigned oi = 0; oi < sizeof(force_ops) / sizeof(force_ops[0]); oi++) {
        int op = force_ops[oi];
        memcpy(prog, original, N);
        prog[1360] = (uint8_t)byte_for(op, 1360);
        mark_fixed(); fixedmask[1360] = 1;
        rebuild_all(); full_resim();
        static uint8_t forced_base[M]; memcpy(forced_base, prog, N);

        int c1[RMAXCELL], n1 = 0;
        for (int a = 1351; a < 1351 + first_span; a++)
            if (!is_fixed(a)) c1[n1++] = a;
        rorder = order1; rstepcap = 100; rnodecap = nodes1;
        int f1 = rsolve(150, c1, n1);
        fprintf(stderr, "op=%d first=%d nodes=%ld%s cells=%d\n", op, f1, rnodes,
                rnodes > rnodecap ? " capped" : "", n1);
        for (int s = 0; s < f1; s++) {
            f_n[s] = rn[s];
            for (int j = 0; j < f_n[s]; j++) {
                f_a[s][j] = raddr[s][j];
                f_b[s][j] = rbyte[s][j];
            }
        }

        for (int s1 = 0; s1 < f1; s1++) {
            memcpy(prog, forced_base, N);
            for (int j = 0; j < f_n[s1]; j++) prog[f_a[s1][j]] = f_b[s1][j];
            rebuild_all(); full_resim();
            if (!solved[150]) continue;
            static uint8_t parent[M]; memcpy(parent, prog, N);

            mark_fixed(); protect_trace(150);
            int c2[RMAXCELL], n2 = 0;
            for (int a = 1360; a < 1360 + second_span; a++)
                if (!is_fixed(a)) c2[n2++] = a;
            rorder = order2; rstepcap = 220; rnodecap = nodes2;
            int f2 = rsolve(151, c2, n2);
            if (!f2) continue;
            fprintf(stderr, "  compatible op=%d first=%d second=%d nodes=%ld cells=%d\n",
                    op, s1, f2, rnodes, n2);
            for (int s2 = 0; s2 < f2; s2++) {
                memcpy(prog, parent, N);
                for (int j = 0; j < rn[s2]; j++) prog[raddr[s2][j]] = rbyte[s2][j];
                rebuild_all(); full_resim();
                if (cur_score > best) {
                    best = cur_score; memcpy(bestprog, prog, N); write_prog(out);
                    fprintf(stderr, "BEST %d/256 op=%d first=%d second=%d misses:",
                            best, op, s1, s2); misses(); fputc('\n', stderr);
                    if (best >= 251) goto done;
                }
            }
        }
    }
done:
    memcpy(prog, bestprog, N); rebuild_all(); full_resim(); write_prog(out);
    fprintf(stderr, "joint final %d/256 misses:", cur_score); misses(); fputc('\n', stderr);
    return best >= 251 ? 0 : 1;
}
