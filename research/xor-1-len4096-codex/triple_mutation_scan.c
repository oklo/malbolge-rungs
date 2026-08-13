/* Exhaustive legal three-cell neighborhood for one failing hero1 input.
 *
 * Completeness pruning: at least one effective edit must touch the baseline
 * trace.  After fixing that edit and an arbitrary second edit, a productive
 * final edit must touch the then-current trace (otherwise execution cannot
 * observe it). */
#ifdef HERO2
#define main hero2_main
#include "../xor-1-len4096-hero2/hero9.c"
#else
#define main hero1_main
#include "../xor-1-len4096-hero1/hero.c"
#endif
#undef main

static int unique_trace_cells(int target, int *out) {
    rec_touch = 1; (void)simulate(target); rec_touch = 0;
    int n = 0;
    for (int i = 0; i < ntl; i++) {
        int a = tl[i], seen = 0;
        if (a < PROLEN || a >= N) continue;
        for (int j = 0; j < n; j++) seen |= out[j] == a;
        if (!seen) out[n++] = a;
    }
    return n;
}

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "triple-best.mal";
    int target = 3, protected_inputs[16], nprotected = 0; N = 2605;
    int shard = 0, nshards = 1, fourth = 0, joint_target = -1;
    int extra_fixed[32], nextra_fixed = 0;
    int blo = -1, bhi = -1;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-prolen") && i + 1 < argc) PROLEN = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-fix") && i + 1 < argc && nextra_fixed < 32)
            extra_fixed[nextra_fixed++] = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-b-lo") && i + 1 < argc) blo = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-b-hi") && i + 1 < argc) bhi = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-target") && i + 1 < argc) target = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-protect") && i + 1 < argc && nprotected < 16)
            protected_inputs[nprotected++] = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-shard") && i + 1 < argc) {
            if (sscanf(argv[++i], "%d/%d", &shard, &nshards) != 2) return 2;
        }
        else if (!strcmp(argv[i], "-fourth")) fourth = 1;
        else if (!strcmp(argv[i], "-joint") && i + 1 < argc) joint_target = atoi(argv[++i]);
        else return 2;
    }
    if (!seed || target < 0 || target > 255 || shard < 0 || shard >= nshards ||
        joint_target > 255) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed();
    for (int i = 0; i < nextra_fixed; i++) fixedmask[extra_fixed[i]] = 1;
    FILE *sf = fopen(seed, "rb"); if (!sf) return 2;
    int got = (int)fread(prog, 1, M, sf); fclose(sf);
    if (got != N) return 2;
    rebuild_all(); full_resim();
    if (blo < 0) blo = PROLEN; if (bhi < 0) bhi = N - 1;
    if (blo < PROLEN || bhi < blo || bhi >= N) return 2;
    int first[128], nf = unique_trace_cells(target, first);
    static uint8_t bestprog[M];
    int best = -1, ba = -1, bb = -1, bc = -1, bd = -1, be = -1;
    int bva = -1, bvb = -1, bvc = -1, bvd = -1, bve = -1;
    unsigned long long tested = 0, solves = 0, pairs = 0, fourths = 0, joint_pairs = 0;
    for (int fi = shard; fi < nf; fi += nshards) {
        int a = first[fi], aa[1] = {a}; uint8_t oa[1] = {prog[a]};
        for (int ka = 0; ka < 8; ka++) {
            uint8_t va[1] = {(uint8_t)byte_for(CODES[ka], a)};
            if (va[0] == oa[0]) continue;
            apply_changes(aa, va, 1);
            for (int b = blo; b <= bhi; b++) if (b != a) {
                int ab[1] = {b}; uint8_t ob[1] = {prog[b]};
                for (int kb = 0; kb < 8; kb++) {
                    uint8_t vb[1] = {(uint8_t)byte_for(CODES[kb], b)};
                    if (vb[0] == ob[0]) continue;
                    apply_changes(ab, vb, 1); pairs++;
                    if (!simulate(target)) {
                        int third[128], nt = unique_trace_cells(target, third);
                        for (int ti = 0; ti < nt; ti++) {
                            int c = third[ti]; if (c == a || c == b) continue;
                            int ac[1] = {c}; uint8_t oc[1] = {prog[c]};
                            for (int kc = 0; kc < 8; kc++) {
                                uint8_t vc[1] = {(uint8_t)byte_for(CODES[kc], c)};
                                if (vc[0] == oc[0]) continue;
                                tested++; apply_changes(ac, vc, 1);
                                if (simulate(target)) {
                                    full_resim();
                                    solves++;
                                    int protected_ok = 1;
                                    for (int p = 0; p < nprotected; p++) protected_ok &= solved[protected_inputs[p]];
                                    /* In joint mode, do not let a target-only
                                     * triple establish the score threshold or
                                     * overwrite the joint output artifact. */
                                    if (joint_target < 0 && protected_ok && cur_score > best) {
                                        best = cur_score; ba = a; bva = va[0]; bb = b; bvb = vb[0];
                                        bc = c; bvc = vc[0]; bd = bvd = -1;
                                        memcpy(bestprog, prog, N); write_prog(out);
                                        fprintf(stderr, "BEST target=%d score=%d/256 %d=%d %d=%d %d=%d misses:",
                                                target, best, a, va[0], b, vb[0], c, vc[0]);
                                        for (int x = 0; x < 256; x++) if (!solved[x]) fprintf(stderr, " %d", x);
                                        fputc('\n', stderr);
                                    }
                                    if (fourth && joint_target < 0) for (int d = PROLEN; d < N; d++) {
                                        if (d == a || d == b || d == c) continue;
                                        int ad[1] = {d}; uint8_t od[1] = {prog[d]};
                                        for (int kd = 0; kd < 8; kd++) {
                                            uint8_t vd[1] = {(uint8_t)byte_for(CODES[kd], d)};
                                            if (vd[0] == od[0]) continue;
                                            fourths++; apply_changes(ad, vd, 1);
                                            protected_ok = solved[target];
                                            for (int p = 0; p < nprotected; p++) protected_ok &= solved[protected_inputs[p]];
                                            if (protected_ok && cur_score > best) {
                                                best = cur_score; ba = a; bva = va[0]; bb = b; bvb = vb[0];
                                                bc = c; bvc = vc[0]; bd = d; bvd = vd[0];
                                                memcpy(bestprog, prog, N); write_prog(out);
                                                fprintf(stderr, "BEST4 target=%d score=%d/256 %d=%d %d=%d %d=%d %d=%d misses:",
                                                        target, best, a, va[0], b, vb[0], c, vc[0], d, vd[0]);
                                                for (int x = 0; x < 256; x++) if (!solved[x]) fprintf(stderr, " %d", x);
                                                fputc('\n', stderr);
                                            }
                                            apply_changes(ad, od, 1);
                                        }
                                    }
                                    if (joint_target >= 0) {
                                        int joint_first[128], nj = unique_trace_cells(joint_target, joint_first);
                                        for (int ji = 0; ji < nj; ji++) {
                                            int d = joint_first[ji];
                                            if (d == a || d == b || d == c) continue;
                                            int ad[1] = {d}; uint8_t od[1] = {prog[d]};
                                            for (int kd = 0; kd < 8; kd++) {
                                                uint8_t vd[1] = {(uint8_t)byte_for(CODES[kd], d)};
                                                if (vd[0] == od[0]) continue;
                                                apply_changes(ad, vd, 1);
                                                for (int e = PROLEN; e < N; e++) {
                                                    if (e == a || e == b || e == c || e == d) continue;
                                                    int ae[1] = {e}; uint8_t oe[1] = {prog[e]};
                                                    for (int ke = 0; ke < 8; ke++) {
                                                        uint8_t ve[1] = {(uint8_t)byte_for(CODES[ke], e)};
                                                        if (ve[0] == oe[0]) continue;
                                                        joint_pairs++; apply_changes(ae, ve, 1);
                                                        protected_ok = solved[target] && solved[joint_target];
                                                        for (int p = 0; p < nprotected; p++) protected_ok &= solved[protected_inputs[p]];
                                                        if (protected_ok && cur_score > best) {
                                                            best = cur_score; ba = a; bva = va[0]; bb = b; bvb = vb[0];
                                                            bc = c; bvc = vc[0]; bd = d; bvd = vd[0]; be = e; bve = ve[0];
                                                            memcpy(bestprog, prog, N); write_prog(out);
                                                            fprintf(stderr, "BEST5 target=%d joint=%d score=%d/256 %d=%d %d=%d %d=%d %d=%d %d=%d misses:",
                                                                    target, joint_target, best, a, va[0], b, vb[0], c, vc[0], d, vd[0], e, ve[0]);
                                                            for (int x = 0; x < 256; x++) if (!solved[x]) fprintf(stderr, " %d", x);
                                                            fputc('\n', stderr);
                                                        }
                                                        apply_changes(ae, oe, 1);
                                                    }
                                                }
                                                apply_changes(ad, od, 1);
                                            }
                                        }
                                    }
                                }
                                apply_changes(ac, oc, 1); full_resim();
                            }
                        }
                    }
                    apply_changes(ab, ob, 1);
                }
            }
            apply_changes(aa, oa, 1);
        }
    }
    fprintf(stderr,
            "target=%d shard=%d/%d first=%d pairs=%llu thirds=%llu solves=%llu fourths=%llu joint-pairs=%llu best=%d %d=%d %d=%d %d=%d %d=%d %d=%d\n",
            target, shard, nshards, nf, pairs, tested, solves, fourths, joint_pairs, best,
            ba, bva, bb, bvb, bc, bvc, bd, bvd, be, bve);
    if (best >= 0) { memcpy(prog, bestprog, N); rebuild_all(); full_resim(); write_prog(out); }
    return best < 0;
}
