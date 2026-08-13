/* Exhaustively vary a short legal prefix and score it in a full classic VM.
 * Unlike hero1's closed-form post-prologue simulator, this deliberately allows
 * the prologue control/data flow to change. */
#define main hero1_main
#include "../xor-1-len4096-hero1/hero.c"
#undef main

static int native_simulate(int b) {
    int base = nund, A = 0, C = 0, D = 0, input_used = 0;
    int outn = 0, outb = -1, ok = 0;
    for (int step = 0; step < 4096; step++) {
        int w = mem[C];
        if (w < 33 || w > 126) break;
        int code = code_of(w, C);
        if (code == HLT) { ok = outn == 1 && outb == (b ^ 0x51); break; }
        switch (code) {
            case JMP: C = mem[D]; break;
            case OUT:
                if (outn++) goto done;
                outb = A & 255; break;
            case IN: A = input_used++ ? M - 1 : b; break;
            case ROT: { int v = rotr(mem[D]); wr(D, v); A = v; break; }
            case MOVD: D = mem[D]; break;
            case CRZ: { int v = crazyw(A, mem[D]); wr(D, v); A = v; break; }
            default: break;
        }
        w = mem[C];
        if (w < 33 || w > 126) break;
        wr(C, X2[w]);
        C = (C + 1) % M; D = (D + 1) % M;
    }
done:
    unwind(base);
    return ok;
}

static void rebuild_raw(void) {
    for (int a = 0; a < N; a++) mem[a] = prog[a];
    for (int a = N; a < M; a++) mem[a] = crazyw(mem[a - 1], mem[a - 2]);
    nund = 0;
}

static uint8_t original[M], bestprog[M];
static int start, width, best = -1, best_b0 = -1, best_changes = 9999, require_b0;
static unsigned long long tested;
static const char *outpath;

static void test_leaf(void) {
    tested++;
    rebuild_raw();
    int score = 0, s0 = 0;
    for (int b = 0; b < 256; b++) {
        int s = native_simulate(b); score += s; if (!b) s0 = s;
    }
    int changes = 0;
    for (int a = start; a < start + width; a++) changes += prog[a] != original[a];
    if ((require_b0 ? (s0 && (score > best || (score == best && changes < best_changes))) :
         (s0 > best_b0 || (s0 == best_b0 && (score > best ||
          (score == best && changes < best_changes)))))) {
        best = score; best_b0 = s0; best_changes = changes;
        memcpy(bestprog, prog, N);
        fprintf(stderr, "BEST b0=%d score=%d/256 changes=%d prefix=", s0, score, changes);
        fwrite(prog + start, 1, width, stderr); fputc('\n', stderr);
        if (outpath) { memcpy(prog, bestprog, N); write_prog(outpath); }
    }
}

static void enumerate(int depth) {
    if (depth == width) { test_leaf(); return; }
    int a = start + depth;
    for (int k = 0; k < 8; k++) {
        prog[a] = (uint8_t)byte_for(CODES[k], a);
        enumerate(depth + 1);
    }
}

int main(int argc, char **argv) {
    const char *seed = NULL; start = 0; width = 4; N = 2605;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-start") && i + 1 < argc) start = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-width") && i + 1 < argc) width = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-require-b0")) require_b0 = 1;
        else return 2;
    }
    if (!seed || start < 0 || width < 1 || width > 10 || start + width > 32) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); init_prog(seed); memcpy(original, prog, N);
    enumerate(0);
    fprintf(stderr, "tested=%llu final b0=%d score=%d/256 changes=%d\n",
            tested, best_b0, best, best_changes);
    return 0;
}
