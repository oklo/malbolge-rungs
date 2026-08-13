/* Exact whole-witness route search for a hero1 tape.  The inherited hero1 DFS
 * predates the JMP-target encipherment fix and is limited to 40 mutable cells,
 * so this tool supplies a corrected, wider DFS without altering that source. */
#define main hero1_main
#include "../xor-1-len4096-hero1/hero.c"
#undef main

#define RMAXCELL 96
#define RMAXSOL 8192

static uint8_t rmut[M], rasg[M];
static int rtarget, rstepcap, rorder;
static long rnodes, rnodecap;
static int rnsol, rncur;
static int rn[RMAXSOL], raddr[RMAXSOL][RMAXCELL];
static uint8_t rbyte[RMAXSOL][RMAXCELL];
static int rcur_addr[RMAXCELL], rcur_byte[RMAXCELL];

static int rrec(int A, int C, int D, int outn, int outb, int steps);

static void rrecord(void) {
    if (rnsol >= RMAXSOL) return;
    rn[rnsol] = rncur;
    for (int i = 0; i < rncur; i++) {
        raddr[rnsol][i] = rcur_addr[i];
        rbyte[rnsol][i] = (uint8_t)rcur_byte[i];
    }
    rnsol++;
}

static int rbranch(int X, int A, int C, int D, int outn, int outb, int steps) {
    if (rncur >= RMAXCELL) return 0;
    int base = nund;
    for (int k = 0; k < 8; k++) {
        int v = byte_for(CODES[(k + rorder) & 7], X);
        wr(X, v);
        rasg[X] = 1;
        rcur_addr[rncur] = X;
        rcur_byte[rncur] = v;
        rncur++;
        int found = rrec(A, C, D, outn, outb, steps);
        rncur--;
        rasg[X] = 0;
        unwind(base);
        if (found && rnsol >= RMAXSOL) return 1;
    }
    return 0;
}

static int rrec(int A, int C, int D, int outn, int outb, int steps) {
    if (++rnodes > rnodecap || steps >= rstepcap) return 0;
    if (rmut[C] && !rasg[C]) return rbranch(C, A, C, D, outn, outb, steps);
    int w = mem[C];
    if (w < 33 || w > 126) return 0;
    int code = code_of(w, C);
    if (code == IN) return 0;
    if (code == HLT) {
        if (outn == 1 && outb == rtarget) {
            rrecord();
            return 1;
        }
        return 0;
    }
    if (code == OUT && (outn >= 1 || (A & 255) != rtarget)) return 0;
    if (code == JMP || code == ROT || code == MOVD || code == CRZ)
        if (rmut[D] && !rasg[D]) return rbranch(D, A, C, D, outn, outb, steps);
    if (code == JMP) {
        int t = mem[D];
        if (rmut[t] && !rasg[t]) return rbranch(t, A, C, D, outn, outb, steps);
    }

    int base = nund;
    int nA = A, nC = C, nD = D, nOn = outn, nOb = outb;
    switch (code) {
        case JMP: nC = mem[D]; break;
        case OUT: nOb = A & 255; nOn = 1; break;
        case ROT: { int v = rotr(mem[D]); wr(D, v); nA = v; break; }
        case MOVD: nD = mem[D]; break;
        case CRZ: { int v = crazyw(A, mem[D]); wr(D, v); nA = v; break; }
        default: break;
    }
    int wc = mem[nC];
    if (wc < 33 || wc > 126) {
        unwind(base);
        return 0;
    }
    wr(nC, X2[wc]);
    int found = rrec(nA, (nC + 1) % M, (nD + 1) % M,
                     nOn, nOb, steps + 1);
    unwind(base);
    return found;
}

static int rsolve(int b, const int *cells, int ncells) {
    memset(rmut, 0, sizeof(rmut));
    memset(rasg, 0, sizeof(rasg));
    for (int i = 0; i < ncells; i++) rmut[cells[i]] = 1;
    rnsol = rncur = 0;
    rnodes = 0;
    rtarget = b ^ 0x51;
    int base = nund;
    wr(71, crazyw(b, 121));
    wr(72, 9 * b);
    rmut[9 * b] = 0;
    int t = mem[9 * b];
    if (t >= 33 && t <= 126) {
        wr(9 * b, X2[t]);
        rrec(9 * b, 9 * b + 1, 73, 0, -1, 0);
    }
    unwind(base);
    return rnsol;
}

static void misses(void) {
    for (int b = 0; b < 256; b++) if (!solved[b]) fprintf(stderr, " %d", b);
}

#ifndef ROUTE_HERO1_NO_MAIN
int main(int argc, char **argv) {
    const char *seed = NULL, *out = "hero1-routed.mal";
    int target = 255, lo = 2323, hi = 2377, ownspan = 8;
    int protected_inputs[16], nprotected = 0;
    int protect_all = 0;
    int avoid = -1;
    int force_addr = -1, force_code = -1;
    N = 2605;
    rstepcap = 220;
    rnodecap = 3000000000L;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-target") && i + 1 < argc) target = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-lo") && i + 1 < argc) lo = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-hi") && i + 1 < argc) hi = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-span") && i + 1 < argc) ownspan = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-steps") && i + 1 < argc) rstepcap = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-nodes") && i + 1 < argc) rnodecap = atol(argv[++i]);
        else if (!strcmp(argv[i], "-order") && i + 1 < argc) rorder = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-protect") && i + 1 < argc && nprotected < 16)
            protected_inputs[nprotected++] = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-protect-all")) protect_all = 1;
        else if (!strcmp(argv[i], "-avoid") && i + 1 < argc) avoid = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-force") && i + 1 < argc &&
                 sscanf(argv[++i], "%d:%d", &force_addr, &force_code) == 2) {}
        else return 2;
    }
    if (!seed || target < 0 || target > 255 || lo < 0 || hi >= N || lo > hi)
        return 2;

    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed();
    init_prog(seed);
    if (force_addr >= 0) {
        if (force_addr >= N) return 2;
        int known = 0;
        for (int k = 0; k < 8; k++) if (CODES[k] == force_code) known = 1;
        if (!known) return 2;
        prog[force_addr] = (uint8_t)byte_for(force_code, force_addr);
        fixedmask[force_addr] = 1;
    }
    rebuild_all();
    full_resim();
    int baseline = cur_score;
    fprintf(stderr, "start %d/256 misses:", baseline); misses(); fputc('\n', stderr);

    for (int pi = 0; pi < (protect_all ? 256 : nprotected); pi++) {
        int b = protect_all ? pi : protected_inputs[pi];
        if (b == target || (protect_all && !solved[b])) continue;
        rec_touch = 1;
        int ok = simulate(b);
        rec_touch = 0;
        if (!ok) {
            fprintf(stderr, "cannot protect unsolved input %d\n", b);
            return 2;
        }
        for (int i = 0; i < ntl; i++)
            if (tl[i] >= 0 && tl[i] < N) fixedmask[tl[i]] = 1;
    }

    int cells[RMAXCELL], ncells = 0;
    int ownlo = 9 * target + 1, ownhi = 9 * target + ownspan;
    for (int a = ownlo; a <= ownhi && a < N; a++)
        if (!is_fixed(a)) cells[ncells++] = a;
    for (int a = lo; a <= hi && a < N; a++)
        if (!is_fixed(a) && (a < ownlo || a > ownhi)) {
            if (ncells >= RMAXCELL) return 2;
            cells[ncells++] = a;
        }

    int found = rsolve(target, cells, ncells);
    fprintf(stderr, "target %d: %d witnesses, %ld nodes%s, %d mutable cells\n",
            target, found, rnodes, rnodes > rnodecap ? " (capped)" : "", ncells);
    int best = -1, best_changes = 9999, best_witness = -1;
    static uint8_t bestprog[M];
    for (int s = 0; s < found; s++) {
        uint8_t save[RMAXCELL];
        int changed = 0;
        for (int i = 0; i < rn[s]; i++) {
            save[i] = prog[raddr[s][i]];
            changed += save[i] != rbyte[s][i];
        }
        apply_changes(raddr[s], rbyte[s], rn[s]);
        int admissible = 1;
        if (avoid >= 0) {
            rec_touch = 1;
            (void)simulate(target);
            rec_touch = 0;
            for (int i = 0; i < ntl; i++) if (tl[i] == avoid) admissible = 0;
        }
        if (admissible && (cur_score > best || (cur_score == best && changed < best_changes))) {
            best = cur_score;
            best_changes = changed;
            best_witness = s;
            memcpy(bestprog, prog, N);
            fprintf(stderr, "best raw=%d witness=%d changed=%d misses:",
                    best, s, changed); misses(); fputc('\n', stderr);
        }
        apply_changes(raddr[s], save, rn[s]);
    }
    if (best_witness < 0) return 1;
    memcpy(prog, bestprog, N);
    rebuild_all();
    full_resim();
    write_prog(out);
    fprintf(stderr, "final %d/256 witness=%d changed=%d misses:",
            cur_score, best_witness, best_changes); misses(); fputc('\n', stderr);
    return solved[target] ? 0 : 1;
}
#endif
