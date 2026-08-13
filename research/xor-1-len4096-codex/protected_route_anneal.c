/* Anneal exact corrected block-route witnesses while preserving selected
 * inputs semantically.  Unlike protected_anneal.c this uses route_hero1.c's
 * JMP-target-correct DFS, so low-input proposals are genuine witnesses. */
#define ROUTE_HERO1_NO_MAIN
#include "route_hero1.c"

static int locked[32], nlocked;
static uint64_t arng = 0x9e3779b97f4a7c15ULL;
static uint64_t arnd(void) {
    arng ^= arng << 13; arng ^= arng >> 7; arng ^= arng << 17;
    return arng;
}
static double arnd01(void) {
    return (double)(arnd() >> 11) / 9007199254740992.0;
}
static int locks_hold(void) {
    for (int i = 0; i < nlocked; i++) if (!solved[locked[i]]) return 0;
    return 1;
}

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "protected-route-anneal.mal";
    int seconds = 60, ownspan = 20, steps = 220, witcap = 1024, order = 0;
    long nodes = 3000000000L;
    double temperature = 0.5;
    N = 2605;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-t") && i + 1 < argc) seconds = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-span") && i + 1 < argc) ownspan = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-steps") && i + 1 < argc) steps = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-nodes") && i + 1 < argc) nodes = atol(argv[++i]);
        else if (!strcmp(argv[i], "-wit") && i + 1 < argc) witcap = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-order") && i + 1 < argc) order = atoi(argv[++i]) & 7;
        else if (!strcmp(argv[i], "-T") && i + 1 < argc) temperature = atof(argv[++i]);
        else if (!strcmp(argv[i], "-r") && i + 1 < argc) arng ^= strtoull(argv[++i], 0, 10) * 0x5851f42d4c957f2dULL;
        else if (!strcmp(argv[i], "-lock") && i + 1 < argc && nlocked < 32)
            locked[nlocked++] = atoi(argv[++i]);
        else return 2;
    }
    if (!seed || !nlocked || ownspan < 1 || ownspan > RMAXCELL || witcap < 1) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); init_prog(seed); rebuild_all(); full_resim();
    if (!locks_hold()) return 2;
    rorder = order; rstepcap = steps; rnodecap = nodes;

    static uint8_t bestprog[M]; memcpy(bestprog, prog, N);
    int best = cur_score;
    long rounds = 0, accepted = 0;
    time_t started = time(NULL);
    fprintf(stderr, "route anneal start %d/256 locks:", best);
    for (int i = 0; i < nlocked; i++) fprintf(stderr, " %d", locked[i]);
    fputc('\n', stderr);

    while (time(NULL) - started < seconds && best < 256) {
        int failing[256], nf = 0;
        for (int b = 0; b < 256; b++) if (!solved[b]) failing[nf++] = b;
        if (!nf) break;
        int b = failing[arnd() % nf];
        int cells[RMAXCELL], nc = 0;
        for (int a = 9 * b + 1; a <= 9 * b + ownspan && a < N; a++)
            if (!is_fixed(a)) cells[nc++] = a;
        rounds++;
        if (!nc) continue;
        int found = rsolve(b, cells, nc);
        full_resim();
        if (!found) continue;
        int base = cur_score, tries = found < witcap ? found : witcap;
        int chosen = -1, chosen_delta = -9999, chosen_changes = 9999;
        for (int q = 0; q < tries; q++) {
            int s = found <= witcap ? q : (int)(arnd() % found);
            uint8_t save[RMAXCELL]; int changed = 0;
            for (int i = 0; i < rn[s]; i++) {
                save[i] = prog[raddr[s][i]];
                changed += save[i] != rbyte[s][i];
            }
            apply_changes(raddr[s], rbyte[s], rn[s]);
            int delta = locks_hold() ? cur_score - base : -9999;
            apply_changes(raddr[s], save, rn[s]);
            if (delta > chosen_delta || (delta == chosen_delta && changed < chosen_changes)) {
                chosen = s; chosen_delta = delta; chosen_changes = changed;
            }
        }
        double frac = (double)(time(NULL) - started) / (double)seconds;
        double temp = temperature * (1.0 - 0.9 * frac);
        if (chosen >= 0 && (chosen_delta >= 0 || arnd01() < exp((double)chosen_delta / temp))) {
            apply_changes(raddr[chosen], rbyte[chosen], rn[chosen]);
            accepted++;
            if (cur_score > best) {
                best = cur_score; memcpy(bestprog, prog, N); write_prog(out);
                fprintf(stderr, "[%lds] BEST %d/256 round=%ld accepted=%ld target=%d delta=%d misses:",
                        (long)(time(NULL) - started), best, rounds, accepted, b, chosen_delta);
                misses(); fputc('\n', stderr);
            }
        }
        if (rounds % 100 == 0 && cur_score < best - 4) {
            memcpy(prog, bestprog, N); rebuild_all(); full_resim();
        }
    }
    memcpy(prog, bestprog, N); rebuild_all(); full_resim(); write_prog(out);
    fprintf(stderr, "route anneal final %d/256 rounds=%ld accepted=%ld misses:", best, rounds, accepted);
    misses(); fputc('\n', stderr);
    return 0;
}
