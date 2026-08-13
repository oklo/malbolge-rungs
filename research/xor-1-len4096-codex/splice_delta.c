#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(int argc, char **argv) {
    if (argc != 5) return 2;
    uint8_t base[59049], before[59049], after[59049];
    FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
    size_t n = fread(base, 1, sizeof(base), f); fclose(f);
    f = fopen(argv[2], "rb"); if (!f) return 2;
    size_t nb = fread(before, 1, sizeof(before), f); fclose(f);
    f = fopen(argv[3], "rb"); if (!f) return 2;
    size_t na = fread(after, 1, sizeof(after), f); fclose(f);
    if (nb != na || n < nb) return 2;
    int changed = 0;
    for (size_t i = 0; i < nb; i++) if (before[i] != after[i]) {
        base[i] = after[i]; changed++;
    }
    f = fopen(argv[4], "wb"); if (!f) return 2;
    if (fwrite(base, 1, n, f) != n) return 2;
    fclose(f);
    fprintf(stderr, "spliced %d-cell delta into %zu-byte base\n", changed, n);
    return 0;
}
