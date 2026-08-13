/* Exact route synthesis for inputs 0..3 after an equivalent longer prologue.
 *
 * prologue_phase_synth.c guarantees the same post-first-pass state as hero1,
 * but its clean candidate has a 34-byte prologue (final JMP at 33).  Setting
 * PROLEN=34 lets the corrected hero1 route DFS model the low input's second
 * pass exactly.  The mutable set combines the four secondary-dispatch/data
 * region with the phase-compatible 3451-byte tape's private extension.
 */
#define RMAXCELL 384
#define RMAXSOL 65536
#define ROUTE_HERO1_NO_MAIN
#include "route_hero1.c"

int main(int argc, char **argv) {
    const char *seed=NULL,*out="low-phase-route.mal";
    int target=0,lo=34,hi=127,xlo=3260,xhi=3448;
    int protected_inputs[16], nprotected=0;
    int guarded_inputs[32], nguarded=0;
    int extra_fixed[32], nextra_fixed=0;
    N=3451; PROLEN=34; rstepcap=180; rnodecap=3000000000L; rorder=0;
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"-s") && i+1<argc) seed=argv[++i];
        else if (!strcmp(argv[i],"-o") && i+1<argc) out=argv[++i];
        else if (!strcmp(argv[i],"-N") && i+1<argc) N=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-prolen") && i+1<argc) PROLEN=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-target") && i+1<argc) target=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-lo") && i+1<argc) lo=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-hi") && i+1<argc) hi=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-xlo") && i+1<argc) xlo=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-xhi") && i+1<argc) xhi=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-steps") && i+1<argc) rstepcap=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-nodes") && i+1<argc) rnodecap=atol(argv[++i]);
        else if (!strcmp(argv[i],"-order") && i+1<argc) rorder=atoi(argv[++i])&7;
        else if (!strcmp(argv[i],"-rseed") && i+1<argc) rseed=strtoull(argv[++i],NULL,0);
        else if (!strcmp(argv[i],"-protect") && i+1<argc && nprotected<16)
            protected_inputs[nprotected++]=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-guard") && i+1<argc && nguarded<32)
            guarded_inputs[nguarded++]=atoi(argv[++i]);
        else if (!strcmp(argv[i],"-fix") && i+1<argc && nextra_fixed<32)
            extra_fixed[nextra_fixed++]=atoi(argv[++i]);
        else return 2;
    }
    if (!seed || target<0 || target>255 || lo<PROLEN || hi>=N || lo>hi ||
        xlo<PROLEN || xhi>=N || xlo>xhi) return 2;
    for (int v=33;v<=126;v++) X2[v]=(uint8_t)XLAT2[v-33];
    FILE *f=fopen(seed,"rb"); if (!f) { perror(seed); return 2; }
    int got=(int)fread(prog,1,M,f); fclose(f);
    if (got!=N) { fprintf(stderr,"seed length %d != N %d\n",got,N); return 2; }
    memset(fixedmask,0,sizeof(fixedmask));
    for (int a=0;a<PROLEN;a++) fixedmask[a]=1;
    /* First-pass equivalence chain and generated-tail phase are structural. */
    fixedmask[40]=fixedmask[42]=fixedmask[62]=fixedmask[71]=fixedmask[72]=fixedmask[73]=fixedmask[123]=1;
    for (int i=0;i<nextra_fixed;i++)
        if (extra_fixed[i]>=0 && extra_fixed[i]<N) fixedmask[extra_fixed[i]]=1;
    fixedmask[N-2]=fixedmask[N-1]=1;
    rebuild_all(); full_resim();
    int baseline=cur_score;
    fprintf(stderr,"start %d/256 target=%d misses:",baseline,target); misses(); fputc('\n',stderr);
    for (int i=0;i<nprotected;i++) if (!solved[protected_inputs[i]]) {
        fprintf(stderr,"cannot protect unsolved input %d\n",protected_inputs[i]); return 2;
    }

    int cells[RMAXCELL],nc=0;
    for (int a=lo;a<=hi;a++) if (!is_fixed(a)) cells[nc++]=a;
    for (int a=xlo;a<=xhi;a++) if (!is_fixed(a)) {
        if (nc>=RMAXCELL) { fprintf(stderr,"mutable set exceeds %d\n",RMAXCELL); return 2; }
        cells[nc++]=a;
    }
    int found=rsolve(target,cells,nc);
    /* rsolve unwinds VM state but its incremental score cache is speculative. */
    full_resim();
    fprintf(stderr,"target=%d witnesses=%d nodes=%ld%s mutable=%d\n",target,found,rnodes,
            rnodes>rnodecap?" capped":"",nc);
    int best=-1,bguard=-1,bchanges=9999,bw=-1; static uint8_t bp[M];
    for (int s=0;s<found;s++) {
        uint8_t save[RMAXCELL]; int changes=0;
        for (int i=0;i<rn[s];i++) { save[i]=prog[raddr[s][i]]; changes+=save[i]!=rbyte[s][i]; }
        apply_changes(raddr[s],rbyte[s],rn[s]);
        full_resim();
        int admissible=solved[target];
        for (int i=0;i<nprotected;i++) admissible &= solved[protected_inputs[i]];
        int guard=0; for (int i=0;i<nguarded;i++) guard+=solved[guarded_inputs[i]];
        if (admissible && (guard>bguard || (guard==bguard &&
            (cur_score>best || (cur_score==best && changes<bchanges))))) {
            best=cur_score; bguard=guard; bchanges=changes; bw=s; memcpy(bp,prog,N);
            fprintf(stderr,"BEST guard=%d/%d raw=%d witness=%d changes=%d misses:",
                    guard,nguarded,best,s,changes); misses(); fputc('\n',stderr);
        }
        apply_changes(raddr[s],save,rn[s]);
        full_resim();
    }
    if (bw<0) return 1;
    memcpy(prog,bp,N); rebuild_all(); full_resim(); write_prog(out);
    fprintf(stderr,"final=%d baseline=%d target=%d guard=%d/%d witness=%d changes=%d misses:",
            cur_score,baseline,target,bguard,nguarded,bw,bchanges); misses(); fputc('\n',stderr);
    return solved[target]?0:1;
}
