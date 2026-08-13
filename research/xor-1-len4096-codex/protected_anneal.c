/* Annealing driver for hero1 that keeps selected input routes semantically
 * valid while repairing the collateral damage from a broad route. */
#define main hero1_original_main
#include "../xor-1-len4096-hero1/hero.c"
#undef main

static int locked_inputs[32], nlocked;

static int locks_hold(void) {
    for (int i = 0; i < nlocked; i++)
        if (!solved[locked_inputs[i]]) return 0;
    return 1;
}

int main(int argc, char **argv) {
    const char *seed = NULL, *out = "protected-anneal.mal";
    int seconds = 60;
    double temperature = 0.8;
    N = 2605; span = 12; stepcap = 100; nodecap = 50000000L;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) seed = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-t") && i + 1 < argc) seconds = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-N") && i + 1 < argc) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-span") && i + 1 < argc) span = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-steps") && i + 1 < argc) stepcap = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-nodes") && i + 1 < argc) nodecap = atol(argv[++i]);
        else if (!strcmp(argv[i], "-T") && i + 1 < argc) temperature = atof(argv[++i]);
        else if (!strcmp(argv[i], "-r") && i + 1 < argc)
            rng_s = strtoull(argv[++i], 0, 10) * 2654435761u + 12345;
        else if (!strcmp(argv[i], "-lock") && i + 1 < argc && nlocked < 32)
            locked_inputs[nlocked++] = atoi(argv[++i]);
        else return 2;
    }
    if (!seed || !nlocked) return 2;
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    mark_fixed(); init_prog(seed); rebuild_all(); full_resim();
    if (!locks_hold()) {
        fprintf(stderr, "seed does not satisfy every lock\n");
        return 2;
    }

    static uint8_t bestprog[M];
    memcpy(bestprog, prog, N);
    int best = cur_score;
    long rounds = 0, since_best = 0;
    time_t started = time(NULL);
    fprintf(stderr, "protected start %d/256 locks:", cur_score);
    for (int i = 0; i < nlocked; i++) fprintf(stderr, " %d", locked_inputs[i]);
    fputc('\n', stderr);

    while (time(NULL) - started < seconds) {
        rounds++;
        int candidates[256], nc = 0;
        for (int b = 0; b < 256; b++) if (!solved[b]) candidates[nc++] = b;
        if (!nc) break;
        take_snap();
        double frac = (double)(time(NULL) - started) / (double)seconds;
        double t = temperature * (1.0 - 0.9 * frac);
        int b = candidates[rnd() % nc];
        (void)try_input(b, t, 0);
        if (!locks_hold()) restore_snap();

        if (cur_score > best) {
            best = cur_score;
            memcpy(bestprog, prog, N);
            since_best = 0;
            fprintf(stderr, "[%3lds] protected best %d/256 round %ld\n",
                    (long)(time(NULL) - started), best, rounds);
        } else if (++since_best > 20000) {
            memcpy(prog, bestprog, N); rebuild_all(); full_resim();
            since_best = 0;
        }
    }
    memcpy(prog, bestprog, N); rebuild_all(); full_resim();
    fprintf(stderr, "protected final %d/256 after %ld rounds; wrong:", cur_score, rounds);
    for (int b = 0; b < 256; b++) if (!solved[b]) fprintf(stderr, " %d", b);
    fputc('\n', stderr);
    write_prog(out);
    return 0;
}
