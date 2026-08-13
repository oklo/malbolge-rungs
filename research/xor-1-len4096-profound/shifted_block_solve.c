/* Exact independent-block solver for build_shifted_dispatch.py.
 *
 * The prologue is simulated rather than summarized.  For byte b it must enter
 * C=9*(b+81)+1 with D=98 and A=9*(b+81).  DFS then assigns only that input's
 * private nine source cells.  Operand reads are allowed from the shared fixed
 * prefix (<729) or from the same block; therefore all witnesses compose.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef BLOCKSPAN
#define BLOCKSPAN 18
#endif
enum { M=59049, NMAX=4096, SPAN=BLOCKSPAN, JMP=4, OUT=5, IN=23, ROT=39,
       MOVD=40, CRZ=62, NOP=68, HLT=81 };
#ifndef OP0
#define OP0 JMP
#define OP1 OUT
#define OP2 ROT
#define OP3 MOVD
#define OP4 CRZ
#define OP5 NOP
#define OP6 HLT
#endif
static const int OPS[7]={OP0,OP1,OP2,OP3,OP4,OP5,OP6};
static const int CT[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static const char X[]="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";

typedef struct { int a; uint16_t v; } Undo;
static uint8_t prog[NMAX],answer[SPAN],answer_used[SPAN],locked[M];static uint16_t base[M],mem[M];static int n;
static int A,C,D,outn,outb,bb,target,assigned[SPAN],pinned[SPAN],touched[SPAN],choice[SPAN];
static long nodes,nodecap=50000000;static int found,depthcap=24,maxdepth=24,start_d=-1,prefix_nops;
static uint8_t exits[M];static int nexits;
static int route_compat,route_exit;static uint16_t partner_pre[M],pmem[M];static uint8_t route_source[SPAN],route_required[SPAN],psource[SPAN],passigned[SPAN];
static int post_addr=-1,post_value;
static int post_a=-1;

static int crazy(int a,int d){int r=0,p=1;for(int i=0;i<10;i++){r+=CT[(d/p)%3][(a/p)%3]*p;p*=3;}return r;}
static int rotr(int w){return w/3+(w%3)*19683;}
static int byte_for(int op,int a){int v=(op-a)%94;if(v<0)v+=94;while(v<33)v+=94;return v;}
static void wr(Undo *u,int *nu,int a,int v){u[*nu]=(Undo){a,mem[a]};(*nu)++;mem[a]=(uint16_t)v;}
static void undo(Undo *u,int nu){while(nu){--nu;mem[u[nu].a]=u[nu].v;}}
static int private(int a){return a>=bb&&a<bb+SPAN;}
static int safe_data(int a){return a<729||private(a);}

static int partner_dfs(int a,int c,int d,int on,int ob,int used,int depth){
    if(depth>=2048)return 0;
    int ci=private(c)?c-bb:-1;
    if(ci>=0&&!passigned[ci]){
        uint16_t save=pmem[c];
        for(int k=0;k<7;k++){psource[ci]=(uint8_t)byte_for(OPS[k],c);pmem[c]=psource[ci];passigned[ci]=1;if(partner_dfs(a,c,d,on,ob,used,depth))return 1;passigned[ci]=0;}
        pmem[c]=save;return 0;
    }
    int w=pmem[c];if(w<33||w>126)return 0;int op=(w+c)%94;
    int di=private(d)?d-bb:-1;
    if((op==JMP||op==ROT||op==MOVD||op==CRZ)&&di>=0&&!passigned[di]){
        uint16_t save=pmem[d];
        for(int k=0;k<7;k++){psource[di]=(uint8_t)byte_for(OPS[k],d);pmem[d]=psource[di];passigned[di]=1;if(partner_dfs(a,c,d,on,ob,used,depth))return 1;passigned[di]=0;}
        pmem[d]=save;return 0;
    }
    Undo u[4];int nu=0;
    if(op==JMP)c=pmem[d];
    else if(op==OUT){if(on||((a&255)!=(217^0x51)))return 0;on=1;ob=a&255;}
    else if(op==IN)a=used++?59048:217;
    else if(op==ROT){int v=rotr(pmem[d]);wr(u,&nu,d,v);a=v;}
    else if(op==MOVD)d=pmem[d];
    else if(op==CRZ){int v=crazy(a,pmem[d]);wr(u,&nu,d,v);a=v;}
    else if(op==HLT){int ok=on==1&&ob==(217^0x51);undo(u,nu);if(ok)for(int i=0;i<SPAN;i++)if(passigned[i])route_source[i]=psource[i];return ok;}
    w=pmem[c];if(w<33||w>126){undo(u,nu);return 0;}wr(u,&nu,c,(uint8_t)X[w-33]);
    int ok=partner_dfs(a,c+1,d+1,on,ob,used,depth+1);undo(u,nu);return ok;
}

static int partner_search(void){
    memcpy(pmem,partner_pre,sizeof pmem);
    for(int i=0;i<SPAN;i++){psource[i]=route_source[i];passigned[i]=route_required[i];if(passigned[i])pmem[bb+i]=psource[i];}
    return partner_dfs(9*(217+81),9*(217+81)+1,42,0,-1,1,0);
}

static int compatible_exit(int x){
    if(outn&&(outn!=1||outb!=target))return 0;
    for(int i=0;i<SPAN;i++){
        route_required[i]=(uint8_t)(assigned[i]||touched[i]||pinned[i]>=0||locked[bb+i]);
        route_source[i]=choice[i]>=0?(uint8_t)choice[i]:prog[bb+i];
    }
    if(!partner_search())return 0;
    route_exit=x;for(int i=0;i<SPAN;i++){answer[i]=route_source[i];answer_used[i]=1;}return 1;
}

static int exec(Undo *u,int *nu){
    int w=mem[C];if(w<33||w>126)return -1;int op=(w+C)%94;
    if((op==JMP||op==ROT||op==MOVD||op==CRZ)&&!safe_data(D))return -1;
    if((op==JMP||op==ROT||op==MOVD||op==CRZ)&&private(D)){
        int i=D-bb;if(pinned[i]<0)pinned[i]=mem[D]<=126?mem[D]:32767;
    }
    if(op==JMP)C=mem[D];
    else if(op==OUT){if(outn++)return -1;outb=A&255;}
    else if(op==IN)return -1;
    else if(op==ROT){int v=rotr(mem[D]);if(private(D))touched[D-bb]=1;wr(u,nu,D,v);A=v;}
    else if(op==MOVD)D=mem[D];
    else if(op==CRZ){int v=crazy(A,mem[D]);if(private(D))touched[D-bb]=1;wr(u,nu,D,v);A=v;}
    else if(op==HLT)return outn==1&&outb==target?1:-1;
    w=mem[C];if(w<33||w>126)return -1;wr(u,nu,C,(uint8_t)X[w-33]);C++;D++;return 0;
}

static void dfs(int depth){
    if(found||++nodes>nodecap||depth>=depthcap)return;
    if(!private(C)){if(C>=3034&&C<4096&&!exits[C]){exits[C]=1;nexits++;}if(route_compat&&C>=3034&&C<4096&&compatible_exit(C))found=1;return;}
    int i=C-bb,cand[7],nc=0;
    if(assigned[i]||touched[i]||locked[C])cand[nc++]=mem[C];
    else if(pinned[i]>=0){if(pinned[i]==32767)return;cand[nc++]=pinned[i];}
    else for(int k=0;k<7;k++)cand[nc++]=byte_for(OPS[k],C);
    int sa=A,sc=C,sd=D,son=outn,sob=outb,sas=assigned[i],sch=choice[i];
    int spin[SPAN],stouch[SPAN];memcpy(spin,pinned,sizeof spin);memcpy(stouch,touched,sizeof stouch);
    for(int k=0;k<nc&&!found;k++){
        Undo u[16];int nu=0;wr(u,&nu,C,cand[k]);
        if(!assigned[i]&&!touched[i]&&pinned[i]<0)choice[i]=cand[k];
        assigned[i]=1;int r=exec(u,&nu);
        if(r==1&&!route_compat){found=1;for(int z=0;z<SPAN;z++){answer_used[z]=(uint8_t)(assigned[z]||touched[z]||pinned[z]>=0||locked[bb+z]);answer[z]=choice[z]>=0?(uint8_t)choice[z]:prog[bb+z];}}
        else if(r==0)dfs(depth+1);
        undo(u,nu);A=sa;C=sc;D=sd;outn=son;outb=sob;assigned[i]=sas;choice[i]=sch;
        memcpy(pinned,spin,sizeof spin);memcpy(touched,stouch,sizeof stouch);
    }
}

static int prologue(int b){
    memcpy(mem,base,sizeof base);A=C=D=outn=0;outb=-1;int used=0;
    int want=9*(b+81)+1;
    for(int s=0;s<700;s++){
        if(C==want){if(A!=want-1&&!(A==3303&&mem[120]==3303))return 0;if(start_d>=0)D=start_d;if(post_addr>=0)mem[post_addr]=(uint16_t)post_value;if(post_a>=0)A=post_a;return 1;}
        int w=mem[C];if(w<33||w>126)return 0;int op=(w+C)%94;
        if(op==JMP)C=mem[D];else if(op==OUT)return 0;else if(op==IN)A=used++?59048:b;
        else if(op==ROT){mem[D]=rotr(mem[D]);A=mem[D];}else if(op==MOVD)D=mem[D];
        else if(op==CRZ){mem[D]=crazy(A,mem[D]);A=mem[D];}else if(op==HLT)return 0;
        w=mem[C];if(w<33||w>126)return 0;mem[C]=(uint8_t)X[w-33];C++;D++;
    }return 0;
}

static int solve(int b){
    bb=9*(b+81)+1;target=b^0x51;found=0;long totalnodes=0;nexits=0;memset(exits,0,sizeof exits);
    for(int i=0;i<prefix_nops&&i<SPAN;i++){int v=byte_for(NOP,bb+i);prog[bb+i]=(uint8_t)v;base[bb+i]=(uint16_t)v;locked[bb+i]=1;}
    for(depthcap=6;depthcap<=maxdepth&&!found;depthcap++){
        if(!prologue(b)){fprintf(stderr,"bad prologue b=%d C=%d D=%d A=%d\n",b,C,D,A);return 0;}
        for(int i=0;i<SPAN;i++){assigned[i]=touched[i]=0;pinned[i]=choice[i]=-1;}
        nodes=0;dfs(0);totalnodes+=nodes;
    }
    if(found){for(int i=0;i<SPAN;i++)if(answer_used[i]){prog[bb+i]=answer[i];base[bb+i]=answer[i];locked[bb+i]=1;}}
    printf("b=%3d ok=%d nodes=%ld depth=%d exits=%d",b,found,totalnodes,depthcap-1,nexits);if(found){printf(" source=");fwrite(answer,1,SPAN,stdout);}else if(nexits){printf(" high=");int k=0;for(int a=3034;a<4096&&k<20;a++)if(exits[a]){printf("%s%d",k?",":"",a);k++;}}putchar('\n');
    return found;
}

int main(int ac,char **av){
    if(ac<3){fprintf(stderr,"usage: %s base.mal out.mal [lo hi nodecap depthcap]\n",av[0]);return 2;}
    int lo=ac>3?atoi(av[3]):0,hi=ac>4?atoi(av[4]):255;if(ac>5)nodecap=atol(av[5]);if(ac>6)maxdepth=atoi(av[6]);if(ac>7)start_d=atoi(av[7]);if(ac>8)prefix_nops=atoi(av[8]);
    FILE *f=fopen(av[1],"rb");if(!f)return 2;n=fread(prog,1,NMAX,f);fclose(f);
    for(int i=0;i<n;i++)base[i]=prog[i];for(int i=n;i<M;i++)base[i]=crazy(base[i-1],base[i-2]);
    route_compat=getenv("ROUTE_COMPAT")!=NULL;
    if(getenv("POST_ADDR")){post_addr=atoi(getenv("POST_ADDR"));post_value=atoi(getenv("POST_VALUE"));}
    if(getenv("POST_A"))post_a=atoi(getenv("POST_A"));
    for(int q=9;q+1<ac;q+=2){int fa=atoi(av[q]),fop=atoi(av[q+1]);if(fa<0||fa>=n)return 2;int fv=byte_for(fop,fa);prog[fa]=(uint8_t)fv;base[fa]=(uint16_t)fv;locked[fa]=1;fprintf(stderr,"forced %d=%d(op%d)\n",fa,fv,fop);}
    if(route_compat){bb=9*(216+81)+1;if(!prologue(217)){fprintf(stderr,"bad partner prologue\n");return 2;}memcpy(partner_pre,mem,sizeof mem);}
    int count=0,step=lo<=hi?1:-1;for(int b=lo;;b+=step){count+=solve(b);if(b==hi)break;}
    f=fopen(av[2],"wb");if(!f)return 2;fwrite(prog,1,n,f);fclose(f);
    int total=abs(hi-lo)+1;fprintf(stderr,"shifted blocks solved=%d/%d nodecap=%ld maxdepth=%d start_d=%d\n",count,total,nodecap,maxdepth,start_d);
    if(route_compat&&found)fprintf(stderr,"ROUTE_COMPAT exit=%d\n",route_exit);
    return count==total?0:1;
}
