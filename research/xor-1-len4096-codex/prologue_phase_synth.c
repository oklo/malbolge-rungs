/* Finite synthesis of an equivalent x9 dispatch prologue.
 *
 * The 253/256 hero1 tape fails 0,1,3 because those inputs redispatch through
 * the already-enciphered 33-cell prologue.  Instead of perturbing the global
 * tape, enumerate short prologues which have exactly the same first-pass
 * semantic post-state:
 *
 *   A = m[72] = 9*b, m[71] = crazy(b,121), D = 72 at the final JMP.
 *
 * The variable prefix contains one IN and MOVD/NOP operations.  Its data-chain
 * choices are enumerated exactly.  The double-CRAZY and eight-rotation suffix
 * remains the proven construction.  Prologue lengths 33..37 keep input 4's
 * private block outside the prologue.  Every candidate is then scored with a
 * full classic-Malbolge VM, in parallel across independent candidates.
 *
 * Build: cc -O3 -std=c11 -pthread -o prologue_phase_synth prologue_phase_synth.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <pthread.h>
#include <stdatomic.h>
#include <limits.h>

#define MEMSZ 59049
#define MAXN 4096
#define MAXCAND 100000000
#define MAXASSIGN 24
#define MAXR 24

enum { JMP=4, OUT=5, IN=23, ROT=39, MOVD=40, CRZ=62, NOP=68, HLT=81 };
static const int CODES[8] = {JMP,OUT,IN,ROT,MOVD,CRZ,NOP,HLT};
static const int CT[3][3] = {{1,0,0},{1,0,2},{2,2,1}};
static const char *XLAT2 =
    "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";

typedef struct {
    uint8_t r, prefix[MAXR], na;
    uint8_t aa[MAXASSIGN], av[MAXASSIGN];
} Candidate;

typedef struct {
    uint8_t *source;
    uint16_t *memory;
} WorkerMem;

static uint8_t base[MAXN], x2[128];
static uint16_t basefull[MEMSZ];
static int nbase;
static Candidate *cands;
static size_t ncands;
static atomic_size_t next_candidate;
static int nthreads = 14;
static int require_low_partner;
static pthread_mutex_t best_mu = PTHREAD_MUTEX_INITIALIZER;
static int best_hi = -1, best_total = -1, best_changes = INT_MAX;
static size_t best_idx;
static int mask_hi[16], mask_total[16], mask_changes[16];
static size_t mask_idx[16];
static int clean_hi[16], clean_total[16], clean_changes[16];
static size_t clean_idx[16];
static unsigned long long hi_hist[253];
static int alt_hi=-1, alt_total=-1, alt_changes=INT_MAX;
static size_t alt_idx;

static int crazyw(int a, int d) {
    int r=0,p=1;
    for (int i=0;i<10;i++) { r += CT[d%3][a%3]*p; a/=3; d/=3; p*=3; }
    return r;
}
static int rotr(int w) { return w/3 + (w%3)*19683; }
static int code_of(int w, int a) { return (w+a)%94; }
static int byte_for(int code, int a) {
    int v=(code-a)%94; if (v<0) v+=94;
    while (v<33) v+=94;
    return v<=126 ? v : -1;
}
static int legal_source(int v, int a) {
    if (v<33 || v>126) return 0;
    int c=code_of(v,a);
    for (int k=0;k<8;k++) if (CODES[k]==c) return 1;
    return 0;
}

static int full_ops(const Candidate *q, uint8_t ops[64]) {
    int p=0;
    for (int i=0;i<q->r;i++) ops[p++]=q->prefix[i];
    ops[p++]=CRZ; ops[p++]=CRZ;
    for (int j=0;j<8;j++) { ops[p++]=MOVD; ops[p++]=MOVD; ops[p++]=ROT; }
    ops[p++]=MOVD; ops[p++]=MOVD; ops[p++]=JMP;
    return p;
}

static int assigned_value(const Candidate *q, int a) {
    for (int i=0;i<q->na;i++) if (q->aa[i]==a) return q->av[i];
    if (a==62) return 71;
    if (a==71 || a==72) return 121;
    if (a==73) return 61;
    return -1;
}

static int is_real_code(int c) {
    for (int k=0;k<8;k++) if (CODES[k]==c) return 1;
    return 0;
}

/* Low inputs enter at 9*b+1 after the first dispatch.  Mark those whose
 * already-enciphered cells are all runtime NOPs through the still-raw JMP. */
static int clean_sled_mask(const Candidate *q) {
    uint8_t ops[64]; int plen=full_ops(q,ops), mask=0;
    for (int b=0;b<4;b++) {
        int clean=1;
        for (int a=9*b+1;a<plen-1;a++) {
            int raw=byte_for(ops[a],a);
            int enc=code_of(x2[raw],a);
            if (is_real_code(enc)) { clean=0; break; }
        }
        if (clean) mask|=1<<b;
    }
    return mask;
}

/* Resolve the value read by a prefix MOVD.  If the cell is unconstrained,
 * branch over all eight loader-legal source values at that address. */
static void walk_prefix(Candidate *q, int pos, int d, int nin);

static void append_candidate(const Candidate *q) {
    if (ncands>=MAXCAND) { fprintf(stderr,"candidate cap exceeded\n"); exit(2); }
    cands[ncands++]=*q;
}

static void branch_read(Candidate *q, int pos, int d, int nin) {
    uint8_t ops[64]; int plen=full_ops(q,ops);
    int v=-1;
    if (d>=0 && d<plen) {
        v=byte_for(ops[d],d);
        if (d<pos) v=x2[v];
    } else {
        v=assigned_value(q,d);
    }
    if (v>=0) { walk_prefix(q,pos+1,v+1,nin); return; }
    if (d<33 || d>=127 || q->na>=MAXASSIGN) return;
    for (int k=0;k<8;k++) {
        int w=byte_for(CODES[k],d); if (w<0) continue;
        q->aa[q->na]=(uint8_t)d; q->av[q->na]=(uint8_t)w; q->na++;
        walk_prefix(q,pos+1,w+1,nin);
        q->na--;
    }
}

static void walk_prefix(Candidate *q, int pos, int d, int nin) {
    if (pos==q->r) {
        if (nin==1 && d==71) append_candidate(q);
        return;
    }
    int op=q->prefix[pos];
    if (op==IN) walk_prefix(q,pos+1,d+1,nin+1);
    else if (op==NOP) walk_prefix(q,pos+1,d+1,nin);
    else if (op==MOVD) branch_read(q,pos,d,nin);
}

static void enumerate_sequences_rec(Candidate *q, int p, int nin) {
    if (p==q->r) {
        if (nin!=1) return;
        q->na=0; walk_prefix(q,0,0,0);
        return;
    }
    /* Exactly one input; NOPs permit phase shifts, MOVDs form the data chain. */
    if (!nin) { q->prefix[p]=IN; enumerate_sequences_rec(q,p+1,1); }
    q->prefix[p]=NOP; enumerate_sequences_rec(q,p+1,nin);
    q->prefix[p]=MOVD; enumerate_sequences_rec(q,p+1,nin);
}

static void build_source(const Candidate *q, uint8_t *src, int *changes) {
    memcpy(src,base,nbase);
    uint8_t ops[64]; int plen=full_ops(q,ops);
    for (int a=0;a<plen;a++) src[a]=(uint8_t)byte_for(ops[a],a);
    src[62]=71; src[71]=121; src[72]=121; src[73]=61;
    for (int i=0;i<q->na;i++) src[q->aa[i]]=q->av[i];
    *changes=0; for (int a=0;a<127 && a<nbase;a++) *changes += src[a]!=base[a];
}

/* Returns 1 only for exactly one correct output followed by HLT.  The loaded
 * memory is shared across the 256 runs of one candidate; speculative writes
 * are logged and unwound, avoiding 256 redundant 59k-cell tail fills. */
static int run_one(uint16_t *m, int b) {
    int ua[4096], un=0; uint16_t uv[4096];
#define WRITE(A,V) do { if (un>=4096) goto failed; ua[un]=(A); uv[un]=m[(A)]; un++; m[(A)]=(uint16_t)(V); } while (0)
    int A=0,C=0,D=0,ins=0,outn=0,outb=-1;
    for (int step=0;step<2048;step++) {
        int w=m[C]; if (w<33 || w>126) goto failed;
        int code=code_of(w,C);
        if (code==JMP) C=m[D];
        else if (code==OUT) { if (outn++) goto failed; outb=A&255; }
        else if (code==IN) { if (ins++) goto failed; A=b; }
        else if (code==ROT) { int v=rotr(m[D]); WRITE(D,v); A=v; }
        else if (code==MOVD) D=m[D];
        else if (code==CRZ) { int v=crazyw(A,m[D]); WRITE(D,v); A=v; }
        else if (code==HLT) {
            int ok=outn==1 && outb==(b^0x51);
            while (un) { --un; m[ua[un]]=uv[un]; }
            return ok;
        }
        int wc=m[C]; if (wc<33 || wc>126) goto failed;
        WRITE(C,x2[wc]); C=(C+1)%MEMSZ; D=(D+1)%MEMSZ;
    }
failed:
    while (un) { --un; m[ua[un]]=uv[un]; }
#undef WRITE
    return 0;
}

static void score_candidate(size_t idx, WorkerMem *wm) {
    Candidate *q=&cands[idx]; int changes;
    build_source(q,wm->source,&changes);
    for (int a=0;a<127 && a<nbase;a++) if (!legal_source(wm->source[a],a)) return;
    /* Workers start from basefull and run_one logs and unwinds every VM write.
     * Candidate differences are confined below address 127, so overwriting
     * that fixed window is sufficient between candidates. */
    for (int a=0;a<127 && a<nbase;a++) wm->memory[a]=wm->source[a];
    int total=0,hi=0,mask=0;
    /* Low-input phase is the scarce resource.  In targeted mode, discard a
     * candidate before its 252 high-input executions unless it solves input
     * zero and at least one other low input. */
    for (int b=0;b<4;b++) {
        int ok=run_one(wm->memory,b);
        total+=ok; if (ok) mask|=1<<b;
    }
    /* Input 2 already has a reconstructed 250-point crossover.  The actual
     * open architectural question is compatibility of 0 with failure 1 or 3. */
    if (require_low_partner && (!(mask&1) || !(mask&10))) return;
    for (int b=4;b<256;b++) { int ok=run_one(wm->memory,b); total+=ok; hi+=ok; }
    pthread_mutex_lock(&best_mu);
    int cmask=clean_sled_mask(q);
    if (hi>=0 && hi<=252) hi_hist[hi]++;
    if (hi>best_hi || (hi==best_hi && (total>best_total ||
        (total==best_total && changes<best_changes)))) {
        best_hi=hi; best_total=total; best_changes=changes; best_idx=idx;
        fprintf(stderr,"BEST total=%d hi=%d mask=%x changes=%d r=%d idx=%zu\n",
                total,hi,mask,changes,q->r,idx);
    }
    if (hi>mask_hi[mask] || (hi==mask_hi[mask] &&
        (total>mask_total[mask] || (total==mask_total[mask] && changes<mask_changes[mask])))) {
        mask_hi[mask]=hi; mask_total[mask]=total; mask_changes[mask]=changes; mask_idx[mask]=idx;
    }
    if (hi>clean_hi[cmask] || (hi==clean_hi[cmask] &&
        (total>clean_total[cmask] || (total==clean_total[cmask] && changes<clean_changes[cmask])))) {
        clean_hi[cmask]=hi; clean_total[cmask]=total; clean_changes[cmask]=changes; clean_idx[cmask]=idx;
    }
    if (changes>0 && (hi>alt_hi || (hi==alt_hi &&
        (total>alt_total || (total==alt_total && changes<alt_changes))))) {
        alt_hi=hi; alt_total=total; alt_changes=changes; alt_idx=idx;
    }
    pthread_mutex_unlock(&best_mu);
}

static void *worker(void *arg) {
    (void)arg;
    WorkerMem wm={malloc(MAXN),malloc(sizeof(uint16_t)*MEMSZ)};
    if (!wm.source || !wm.memory) exit(2);
    memcpy(wm.memory,basefull,sizeof(basefull));
    for (;;) {
        size_t i=atomic_fetch_add(&next_candidate,1);
        if (i>=ncands) break;
        score_candidate(i,&wm);
    }
    free(wm.source); free(wm.memory); return NULL;
}

static void write_candidate(const char *path, size_t idx) {
    uint8_t src[MAXN]; int changes; build_source(&cands[idx],src,&changes);
    FILE *f=fopen(path,"wb"); if (!f) { perror(path); exit(2); }
    fwrite(src,1,nbase,f); fclose(f);
}

int main(int argc,char **argv) {
    const char *seed=NULL,*out="prologue-phase-best.mal",*classes=NULL;
    int rmin=4,rmax=8;
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"-s") && i+1<argc) seed=argv[++i];
        else if (!strcmp(argv[i],"-o") && i+1<argc) out=argv[++i];
        else if (!strcmp(argv[i],"-classes") && i+1<argc) classes=argv[++i];
        else if (!strcmp(argv[i],"-j") && i+1<argc) nthreads=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-rmin") && i+1<argc) rmin=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-rmax") && i+1<argc) rmax=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-low-partner")) require_low_partner=1;
        else return 2;
    }
    if (!seed || nthreads<1 || nthreads>64 || rmin<1 || rmax<rmin || rmax>MAXR) return 2;
    FILE *f=fopen(seed,"rb"); if (!f) { perror(seed); return 2; }
    nbase=(int)fread(base,1,MAXN,f); fclose(f);
    if (nbase<2305 || nbase>MAXN) return 2;
    for (int a=0;a<nbase;a++) basefull[a]=base[a];
    for (int a=nbase;a<MEMSZ;a++) basefull[a]=(uint16_t)crazyw(basefull[a-1],basefull[a-2]);
    for (int v=33;v<=126;v++) x2[v]=(uint8_t)XLAT2[v-33];
    cands=malloc(sizeof(Candidate)*MAXCAND); if (!cands) return 2;
    for (int m=0;m<16;m++) {
        mask_hi[m]=clean_hi[m]=-1; mask_total[m]=clean_total[m]=-1;
        mask_changes[m]=clean_changes[m]=INT_MAX;
    }
    for (int r=rmin;r<=rmax;r++) {
        Candidate q={0}; q.r=(uint8_t)r; enumerate_sequences_rec(&q,0,0);
    }
    fprintf(stderr,"enumerated %zu exact prologue/data-chain candidates; scoring with %d threads\n",ncands,nthreads);
    pthread_t th[64];
    for (int i=0;i<nthreads;i++) pthread_create(&th[i],NULL,worker,NULL);
    for (int i=0;i<nthreads;i++) pthread_join(th[i],NULL);
    write_candidate(out,best_idx);
    fprintf(stderr,"FINAL total=%d hi=%d changes=%d idx=%zu out=%s\n",
            best_total,best_hi,best_changes,best_idx,out);
    for (int h=252;h>=0;h--) if (hi_hist[h])
        fprintf(stderr,"HIST hi=%d candidates=%llu\n",h,hi_hist[h]);
    if (classes && alt_hi>=0) {
        char p[1024]; snprintf(p,sizeof(p),"%s-alt.mal",classes);
        write_candidate(p,alt_idx);
        fprintf(stderr,"ALT total=%d hi=%d changes=%d idx=%zu out=%s\n",
                alt_total,alt_hi,alt_changes,alt_idx,p);
    }
    if (classes) for (int m=0;m<16;m++) if (mask_hi[m]>=0) {
        char p[1024]; snprintf(p,sizeof(p),"%s-mask%02x.mal",classes,m);
        write_candidate(p,mask_idx[m]);
        fprintf(stderr,"CLASS mask=%x total=%d hi=%d changes=%d idx=%zu out=%s\n",
                m,mask_total[m],mask_hi[m],mask_changes[m],mask_idx[m],p);
    }
    if (classes) for (int m=0;m<16;m++) if (clean_hi[m]>=0) {
        char p[1024]; snprintf(p,sizeof(p),"%s-clean%02x.mal",classes,m);
        write_candidate(p,clean_idx[m]);
        fprintf(stderr,"CLEAN mask=%x total=%d hi=%d changes=%d idx=%zu out=%s\n",
                m,clean_total[m],clean_hi[m],clean_changes[m],clean_idx[m],p);
    }
    return 0;
}
