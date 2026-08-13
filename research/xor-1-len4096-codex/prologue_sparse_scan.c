/* Exhaustive one- and two-cell legal mutations anywhere in the 33-byte
 * prologue, scored with a full classic VM so altered control flow is valid. */
#define main hero1_main
#include "../xor-1-len4096-hero1/hero.c"
#undef main

static int vm(int b) {
    int base = nund, A = 0, C = 0, D = 0, used = 0, outn = 0, outb = -1, ok = 0;
    for (int step = 0; step < 4096; step++) {
        int w = mem[C]; if (w < 33 || w > 126) break;
        int code = code_of(w, C);
        if (code == HLT) { ok = outn == 1 && outb == (b ^ 0x51); break; }
        switch (code) {
            case JMP: C = mem[D]; break;
            case OUT: if (outn++) goto done; outb = A & 255; break;
            case IN: A = used++ ? M - 1 : b; break;
            case ROT: { int v = rotr(mem[D]); wr(D, v); A = v; break; }
            case MOVD: D = mem[D]; break;
            case CRZ: { int v = crazyw(A, mem[D]); wr(D, v); A = v; break; }
            default: break;
        }
        w = mem[C]; if (w < 33 || w > 126) break;
        wr(C, X2[w]); C = (C + 1) % M; D = (D + 1) % M;
    }
done: unwind(base); return ok;
}

static void raw(void) {
    for (int a = 0; a < N; a++) mem[a] = prog[a];
    for (int a = N; a < M; a++) mem[a] = crazyw(mem[a - 1], mem[a - 2]);
    nund = 0;
}

static uint8_t bestprog[M];
static int best = -1, best_changes = 999;
static const char *outpath;
static unsigned long long tested, solves;

static void score(int changes) {
    tested++; raw();
    int s = 0, s0 = 0;
    for (int b = 0; b < 256; b++) { int x = vm(b); s += x; if (!b) s0 = x; }
    if (!s0) return;
    solves++;
    if (s > best || (s == best && changes < best_changes)) {
        best = s; best_changes = changes; memcpy(bestprog, prog, N);
        fprintf(stderr, "BEST b0 score=%d/256 changes=%d prologue=", s, changes);
        fwrite(prog, 1, 33, stderr); fputc('\n', stderr);
        if (outpath) write_prog(outpath);
    }
}

int main(int argc, char **argv) {
    const char *seed = NULL; N = 2605;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else return 2;
    }
    if (!seed) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); init_prog(seed);
    static uint8_t base[M]; memcpy(base, prog, N);
    for (int a = 0; a < 33; a++) {
        for (int ka = 0; ka < 8; ka++) {
            int va = byte_for(CODES[ka], a); if (va == base[a]) continue;
            prog[a] = (uint8_t)va; score(1);
        }
        prog[a] = base[a];
    }
    for (int a = 0; a < 33; a++) for (int b = a + 1; b < 33; b++) {
        for (int ka = 0; ka < 8; ka++) {
            int va = byte_for(CODES[ka], a); if (va == base[a]) continue;
            prog[a] = (uint8_t)va;
            for (int kb = 0; kb < 8; kb++) {
                int vb = byte_for(CODES[kb], b); if (vb == base[b]) continue;
                prog[b] = (uint8_t)vb; score(2);
            }
            prog[b] = base[b];
        }
        prog[a] = base[a];
    }
    fprintf(stderr, "tested=%llu b0-solves=%llu best=%d/256 changes=%d\n",
            tested, solves, best, best_changes);
    if (best >= 0 && outpath) { memcpy(prog, bestprog, N); write_prog(outpath); }
    return best < 0;
}
