/* Joint exact solver for one nine-cell dispatcher block and a private tail.
 *
 * Some inputs cannot halt inside their nine source cells, but can jump to a
 * high, otherwise-unused source address.  Search both islands at once.  This
 * keeps the safe dispatch proof intact and gives each exceptional input a
 * disjoint continuation region in 3034..4095.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef TAILSPAN
#define TAILSPAN 27
#endif
#ifndef BLOCKSPAN
#define BLOCKSPAN 9
#endif
enum { M=59049, NMAX=4096, BS=BLOCKSPAN, RS=BS+TAILSPAN,
       JMP=4, OUT=5, IN=23, ROT=39, MOVD=40, CRZ=62, NOP=68, HLT=81 };
static const int OPS[7]={JMP,OUT,ROT,MOVD,CRZ,NOP,HLT};
static const int CT[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static const char X[]="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
typedef struct { int a; uint16_t v; } Undo;

static uint8_t prog[NMAX],answer[RS],answer_used[RS],locked[NMAX];
static uint16_t base[M],mem[M];
static int n,bb,tb,target,A,C,D,outn,outb;
static int assigned[RS],pinned[RS],touched[RS],choice[RS];
static long long nodes,nodecap=1000000000LL;
static int found,depthcap,maxdepth=32;

static int crazy(int a,int d){int r=0,p=1;for(int i=0;i<10;i++){r+=CT[(d/p)%3][(a/p)%3]*p;p*=3;}return r;}
static int rotr(int w){return w/3+(w%3)*19683;}
static int byte_for(int op,int a){int v=(op-a)%94;if(v<0)v+=94;while(v<33)v+=94;return v;}
static void wr(Undo *u,int *nu,int a,int v){u[*nu]=(Undo){a,mem[a]};(*nu)++;mem[a]=(uint16_t)v;}
static void undo(Undo *u,int nu){while(nu){--nu;mem[u[nu].a]=u[nu].v;}}
static int ri(int a){if(a>=bb&&a<bb+BS)return a-bb;if(a>=tb&&a<tb+TAILSPAN)return BS+a-tb;return -1;}
static int addr_of(int i){return i<BS?bb+i:tb+i-BS;}
static int safe_data(int a){return a<729||ri(a)>=0;}

static int exec(Undo *u,int *nu){
    int w=mem[C];if(w<33||w>126)return -1;int op=(w+C)%94;
    if((op==JMP||op==ROT||op==MOVD||op==CRZ)&&!safe_data(D))return -1;
    int di=ri(D);
    if((op==JMP||op==ROT||op==MOVD||op==CRZ)&&di>=0&&pinned[di]<0)
        pinned[di]=mem[D]<=126?mem[D]:32767;
    if(op==JMP)C=mem[D];
    else if(op==OUT){if(outn++)return -1;outb=A&255;}
    else if(op==IN)return -1;
    else if(op==ROT){int v=rotr(mem[D]);if(di>=0)touched[di]=1;wr(u,nu,D,v);A=v;}
    else if(op==MOVD)D=mem[D];
    else if(op==CRZ){int v=crazy(A,mem[D]);if(di>=0)touched[di]=1;wr(u,nu,D,v);A=v;}
    else if(op==HLT)return outn==1&&outb==target?1:-1;
    w=mem[C];if(w<33||w>126)return -1;wr(u,nu,C,(uint8_t)X[w-33]);C++;D++;return 0;
}

static void dfs(int depth){
    if(found||++nodes>nodecap||depth>=depthcap)return;
    int i=ri(C);if(i<0)return;
    int cand[7],nc=0;
    if(assigned[i]||touched[i]||locked[C])cand[nc++]=mem[C];
    else if(pinned[i]>=0){if(pinned[i]==32767)return;cand[nc++]=pinned[i];}
    else for(int k=0;k<7;k++)cand[nc++]=byte_for(OPS[k],C);
    int sa=A,sc=C,sd=D,son=outn,sob=outb,sas=assigned[i],sch=choice[i];
    int spin[RS],stouch[RS];memcpy(spin,pinned,sizeof spin);memcpy(stouch,touched,sizeof stouch);
    for(int k=0;k<nc&&!found;k++){
        Undo u[16];int nu=0;wr(u,&nu,C,cand[k]);
        if(!assigned[i]&&!touched[i]&&pinned[i]<0)choice[i]=cand[k];
        assigned[i]=1;int r=exec(u,&nu);
        if(r==1){found=1;for(int z=0;z<RS;z++){answer_used[z]=(uint8_t)(assigned[z]||touched[z]||pinned[z]>=0);answer[z]=choice[z]>=0?(uint8_t)choice[z]:prog[addr_of(z)];}}
        else if(r==0)dfs(depth+1);
        undo(u,nu);A=sa;C=sc;D=sd;outn=son;outb=sob;assigned[i]=sas;choice[i]=sch;
        memcpy(pinned,spin,sizeof spin);memcpy(touched,stouch,sizeof stouch);
    }
}

static int prologue(int b){
    memcpy(mem,base,sizeof base);A=C=D=outn=0;outb=-1;int used=0,want=9*(b+81)+1;
    for(int s=0;s<800;s++){
        if(C==want)return (A==want-1||(A==3303&&mem[120]==3303))&&D==42;
        int w=mem[C];if(w<33||w>126)return 0;int op=(w+C)%94;
        if(op==JMP)C=mem[D];else if(op==OUT)return 0;else if(op==IN)A=used++?59048:b;
        else if(op==ROT){mem[D]=rotr(mem[D]);A=mem[D];}else if(op==MOVD)D=mem[D];
        else if(op==CRZ){mem[D]=crazy(A,mem[D]);A=mem[D];}else if(op==HLT)return 0;
        w=mem[C];if(w<33||w>126)return 0;mem[C]=(uint8_t)X[w-33];C++;D++;
    }return 0;
}

int main(int ac,char **av){
    if(ac<5){fprintf(stderr,"usage: %s base.mal out.mal byte tail_start [nodecap depth]\n",av[0]);return 2;}
    int b=atoi(av[3]);tb=atoi(av[4]);if(ac>5)nodecap=atoll(av[5]);if(ac>6)maxdepth=atoi(av[6]);
    if(tb<3034||tb+TAILSPAN>NMAX){fprintf(stderr,"bad tail region\n");return 2;}
    FILE *f=fopen(av[1],"rb");if(!f)return 2;n=fread(prog,1,NMAX,f);fclose(f);
    for(int i=0;i<n;i++)base[i]=prog[i];for(int i=n;i<M;i++)base[i]=crazy(base[i-1],base[i-2]);
    for(int q=7;q+1<ac;q+=2){int fa=atoi(av[q]),fop=atoi(av[q+1]);if(fa<0||fa>=n)return 2;int fv=byte_for(fop,fa);prog[fa]=(uint8_t)fv;base[fa]=(uint16_t)fv;locked[fa]=1;fprintf(stderr,"forced %d=%d(op%d)\n",fa,fv,fop);}
    bb=9*(b+81)+1;target=b^0x51;found=0;
    if(getenv("LOCK_BLOCK"))for(int a=bb;a<bb+BS;a++)locked[a]=1;
    for(depthcap=6;depthcap<=maxdepth&&!found;depthcap++){
        if(!prologue(b)){fprintf(stderr,"bad prologue b=%d C=%d D=%d A=%d\n",b,C,D,A);return 2;}
        for(int i=0;i<RS;i++){assigned[i]=touched[i]=0;pinned[i]=choice[i]=-1;}
        nodes=0;dfs(0);fprintf(stderr,"b=%d tail=%d depth=%d nodes=%lld found=%d\n",b,tb,depthcap,nodes,found);
    }
    if(found)for(int i=0;i<RS;i++)if(answer_used[i]){int a=addr_of(i);prog[a]=answer[i];base[a]=answer[i];}
    f=fopen(av[2],"wb");if(!f)return 2;fwrite(prog,1,n,f);fclose(f);
    if(found){printf("SOLVED b=%d tail=%d block=",b,tb);fwrite(answer,1,BS,stdout);printf(" tail=");fwrite(answer+BS,1,TAILSPAN,stdout);putchar('\n');}
    return found?0:1;
}
