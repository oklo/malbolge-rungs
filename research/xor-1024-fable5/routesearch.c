/* Fable 5 run-4: joint router/table optimization for L2.X1024.xor-1-len1024.
 *
 * Finding: with the retained compact schedule [386,80,108,146,278,272,20,7],
 * the exact overlap DP scores 256/256 when the v5 return alphabet is
 * unrestricted; the binding constraint is which v5 bytes route D back to the
 * absorbing root 41 within 6 MOVDs at every pass boundary. The 53 free low
 * cells (never executed, never read by the prefix, input-independent) are the
 * router. This tool anneals their loader-legal byte assignments; the
 * objective is the exact DP score under the alphabet each assignment induces.
 * Route model validated: reproduces astra allowed.txt bit-for-bit at the base
 * assignment. The native VM stays the judge of any assembled program.
 *
 * usage: routesearch <outdir> <threads> [wildcard]
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <math.h>

static const int ops[8]={4,5,23,39,40,62,68,81};
static int ct[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static int cv(int a,int d){int v=0,p=1;for(int i=0;i<10;i++,p*=3){v+=ct[d%3][a%3]*p;a/=3;d/=3;}return v;}
static int rot_(int a){return a/3+a%3*19683;}
static int byte_(int op,int addr){int v=(op-addr)%94;if(v<0)v+=94;while(v<33)v+=94;return v;}

#define OFFSET 244
#define ROOT 41
#define NB 7            /* pass boundaries */
#define DEPTH 6         /* absorb within 6 MOVDs */
static int MASKS0[8]={386,80,108,146,278,272,20,7};
#define NPASS 8

static uint16_t t5[243][243];
static inline int fastcr(int a,int d){return t5[a%243][d%243]+243*t5[a/243][d/243];}
static int vals[256][7][8];
static uint8_t base_prog[2048]; static int base_len;
static int core=134, retlen=9, retops[16]={40,40,40,40,40,40,40,68,40};
static int snaps[NB][244];
static int input_dep[244];      /* 42,54,61,62,71,72 */
static int nF; static int Faddr[64]; static int Flegal[64][8];
static int Fidx[244];           /* addr -> F index or -1 */

static inline int fastcircuit(const int*MK,int a,int m0,int m1,int m2,int m3,int m4){
 int m[5]={m0,m1,m2,m3,m4};
 for(int p=0;p<NPASS;p++)for(int i=0;i<5;i++)if(!(MK[p]&(1<<(i+5))))a=m[i]=(MK[p]&(1<<i))?rot_(m[i]):fastcr(a,m[i]);
 return a;
}

/* derive allowed[res] bitmask for an F assignment (av[i] = byte at Faddr[i]).
 * wildcard mode: F cells match any target (per-bit optimistic upper bound). */
static void derive_allowed(const int*av,int wildcard,unsigned*allowed){
 for(int res=0;res<94;res++){
  unsigned m=0;
  for(int j=0;j<8;j++){
   int v=byte_(ops[j],res),okall=1;
   for(int t=0;t<NB&&okall;t++){
    int d=v+1,ok=0;
    for(int i=0;i<=DEPTH;i++){
     if(d==ROOT){ok=1;break;}
     if(d>=244||input_dep[d])break;
     int w = (d<244&&Fidx[d]>=0)? av[Fidx[d]] : snaps[t][d];
     if(wildcard&&d<244&&Fidx[d]>=0){ok=2;break;} /* wildcard: assume routable */
     if(w<33||w>126)break;
     d=w+1;
    }
    if(!ok)okall=0;
   }
   if(okall)m|=1u<<j;
  }
  allowed[res]=m;
 }
}

static int eval_dp(const int*MK,const unsigned*allowed, uint8_t *table_out, uint16_t (*prevbuf)[4096]){
 int dp[4096],next[4096];
 for(int s=0;s<4096;s++)dp[s]=0;
 for(int b=0;b<256;b++){
  for(int ns=0;ns<4096;ns++)next[ns]=-10000;
  unsigned al=allowed[(OFFSET+3*b+5)%94];
  for(int s=0;s<4096;s++){
   if(dp[s]<0)continue;
   for(int p=0;p<8;p++){
    int a=fastcircuit(MK,3*b+243,vals[b][0][s/512],vals[b][1][s/64%8],vals[b][2][s/8%8],vals[b][3][s%8],vals[b][4][p]);
    for(int j=0;j<8;j++)if(al&(1u<<j)){
     int aa=fastcr(a,vals[b][5][j]);
     for(int k=0;k<8;k++){
      int w=fastcr(aa,vals[b][6][k])&255,ok=w==(b^81),ns=((s%8)*64+p*8+j)*8+k;
      if(dp[s]+ok>next[ns]){next[ns]=dp[s]+ok;if(prevbuf)prevbuf[b][ns]=s;}
     }
    }
   }
  }
  memcpy(dp,next,sizeof dp);
 }
 int best=0;for(int s=1;s<4096;s++)if(dp[s]>dp[best])best=s;
 if(table_out&&prevbuf){
  int st=best;
  for(int b=255;b>=0;b--){int ps=prevbuf[b][st];
   for(int i=0;i<4;i++){int div=i==0?512:i==1?64:i==2?8:1;
    table_out[3*b+i]=byte_(ops[ps/div%8],OFFSET+3*b+i);
    table_out[3*b+3+i]=byte_(ops[st/div%8],OFFSET+3*b+3+i);}
   st=ps;}
 }
 return dp[best];
}

static int assemble(const int*MK,const int*av,const uint8_t*table,uint8_t*out){
 memcpy(out,base_prog,2048);
 for(int i=0;i<nF;i++)out[Faddr[i]]=av[i];
 memcpy(out+OFFSET,table,772);
 int end=core;
 for(int pass=0;pass<NPASS;pass++){
  if(pass){for(int j=0;j<retlen;j++){out[end]=byte_(retops[j],end);end++;}}
  for(int j=0;j<5;j++){int op=(MK[pass]&(1<<(j+5)))?68:(MK[pass]&(1<<j))?39:62;out[end]=byte_(op,end);end++;}
 }
 int tail[4]={62,62,5,81};for(int j=0;j<4;j++){out[end]=byte_(tail[j],end);end++;}
 if(end>OFFSET)return -1;
 return 1016;
}

static pthread_mutex_t lk=PTHREAD_MUTEX_INITIALIZER;
static int gbest=0; static long gevals=0;
static const char*outdir;
static FILE*loghi;
static unsigned long xs(unsigned long*s){*s^=*s<<13;*s^=*s>>7;*s^=*s<<17;return *s;}

static void report(const int*MK,const int*av,int sc,int bits){
 pthread_mutex_lock(&lk);
 gevals++;
 if(sc>=253){
  fprintf(loghi,"{\"score\":%d,\"bits\":%d,\"masks\":[",sc,bits);for(int i=0;i<NPASS;i++)fprintf(loghi,"%s%d",i?",":"",MK[i]);fprintf(loghi,"],\"av\":[");
  for(int i=0;i<nF;i++)fprintf(loghi,"%s%d",i?",":"",av[i]);
  fprintf(loghi,"]}\n");fflush(loghi);
 }
 if(sc>gbest){
  gbest=sc;
  fprintf(stderr,"[best] score=%d bits=%d evals=%ld\n",sc,bits,gevals);
  static uint16_t (*pv)[4096]=NULL; if(!pv)pv=malloc(256*4096*2);
  unsigned allowed[94];derive_allowed(av,0,allowed);
  uint8_t table[772],prog[2048];
  eval_dp(MK,allowed,table,pv);
  if(assemble(MK,av,table,prog)==1016){
   char fn[512];snprintf(fn,sizeof fn,"%s/rt_best_%d.mal",outdir,sc);
   FILE*f=fopen(fn,"wb");fwrite(prog,1,1016,f);fclose(f);
   snprintf(fn,sizeof fn,"%s/rt_best_%d.av",outdir,sc);
   f=fopen(fn,"w");fprintf(f,"masks ");for(int i=0;i<NPASS;i++)fprintf(f,"%d,",MK[i]);fprintf(f,"\n");
   for(int i=0;i<nF;i++)fprintf(f,"%d %d\n",Faddr[i],av[i]);fclose(f);
  }
 }
 pthread_mutex_unlock(&lk);
}

typedef struct{unsigned long seed;int tid;}targ_t;
static void*worker(void*arg){
 targ_t*ta=arg;unsigned long rng=ta->seed;
 int av[64],bestav[64],MK[8],bestMK[8];
 for(int i=0;i<nF;i++)av[i]=base_prog[Faddr[i]];
 for(int i=0;i<NPASS;i++)MK[i]=MASKS0[i];
 unsigned allowed[94];
 derive_allowed(av,0,allowed);
 int csc=eval_dp(MK,allowed,NULL,NULL);
 int cbits=0;for(int r=0;r<94;r++)cbits+=__builtin_popcount(allowed[r]);
 report(MK,av,csc,cbits);
 int bsc=csc;memcpy(bestav,av,sizeof av);memcpy(bestMK,MK,sizeof MK);
 long iter=0;
 for(;;iter++){
  int navv[64],NMK[8];memcpy(navv,av,sizeof navv);memcpy(NMK,MK,sizeof NMK);
  int mv=getenv("ROUTES_FONLY")?xs(&rng)%45:xs(&rng)%100;
  if(mv<45){int n=1+(xs(&rng)%100<25);for(int c=0;c<n;c++){int i=xs(&rng)%nF;navv[i]=Flegal[i][xs(&rng)%8];}}
  else if(mv<75){int p=xs(&rng)%NPASS;int nb=1+xs(&rng)%2;for(int i=0;i<nb;i++)NMK[p]^=1<<(xs(&rng)%10);}
  else if(mv<90){NMK[xs(&rng)%NPASS]=xs(&rng)%1024;}
  else {int i=xs(&rng)%nF;navv[i]=Flegal[i][xs(&rng)%8];int p=xs(&rng)%NPASS;NMK[p]^=1<<(xs(&rng)%10);}
  derive_allowed(navv,0,allowed);
  int nb2=0;for(int r=0;r<94;r++)nb2+=__builtin_popcount(allowed[r]);
  int nsc=eval_dp(NMK,allowed,NULL,NULL);
  report(NMK,navv,nsc,nb2);
  double T=0.7+0.5*((iter/500)%3);
  long sc_c=(long)csc*10000+cbits, sc_n=(long)nsc*10000+nb2;
  if(sc_n>=sc_c||(double)(xs(&rng)%10000)/10000.0<exp((sc_n-sc_c)/(T*10000.0))){memcpy(av,navv,sizeof navv);memcpy(MK,NMK,sizeof MK);csc=nsc;cbits=nb2;}
  if(csc>bsc){bsc=csc;memcpy(bestav,av,sizeof av);memcpy(bestMK,MK,sizeof MK);}
  if(iter%600==599){memcpy(av,bestav,sizeof av);memcpy(MK,bestMK,sizeof MK);
   for(int c=0;c<2;c++){int i=xs(&rng)%nF;av[i]=Flegal[i][xs(&rng)%8];}
   MK[xs(&rng)%NPASS]^=1<<(xs(&rng)%10);
   derive_allowed(av,0,allowed);csc=eval_dp(MK,allowed,NULL,NULL);
   cbits=0;for(int r=0;r<94;r++)cbits+=__builtin_popcount(allowed[r]);
  }
 }
 return NULL;
}
int main(int argc,char**argv){
 outdir=argv[1];
 int nthreads=argc>2?atoi(argv[2]):8;
 int wildcard=argc>3&&!strcmp(argv[3],"wildcard");
 FILE*f=fopen("research/astra-xor1024-compact-2026-09-06/base.mal","rb");
 base_len=fread(base_prog,1,2048,f);fclose(f);
 f=fopen("research/xor-1024-fable5/snaps.txt","r");
 for(int t=0;t<NB;t++)for(int i=0;i<244;i++)fscanf(f,"%d",&snaps[t][i]);fclose(f);
 memset(input_dep,0,sizeof input_dep);
 int dep[6]={42,54,61,62,71,72};for(int i=0;i<6;i++)input_dep[dep[i]]=1;
 /* free cells from freecells.json (parsed crudely: numbers after "F":) */
 {char buf[8192];f=fopen("research/xor-1024-fable5/freecells.json","r");
  int n=fread(buf,1,sizeof buf-1,f);buf[n]=0;fclose(f);
  char*p=strstr(buf,"\"F\":");p=strchr(p,'[');p++;
  nF=0;while(*p&&*p!=']'){Faddr[nF++]=strtol(p,&p,10);while(*p==','||*p==' ')p++;}
 }
 for(int i=0;i<244;i++)Fidx[i]=-1;
 for(int i=0;i<nF;i++){Fidx[Faddr[i]]=i;
  for(int j=0;j<8;j++)Flegal[i][j]=byte_(ops[j],Faddr[i]);}
 for(int a=0;a<243;a++)for(int d=0;d<243;d++)t5[a][d]=cv(a,d)%243;
 for(int b=0;b<256;b++)for(int i=0;i<7;i++)for(int j=0;j<8;j++)vals[b][i][j]=byte_(ops[j],OFFSET+3*b+i);
 if(getenv("ROUTES_MASKS")){char tmp[256];strncpy(tmp,getenv("ROUTES_MASKS"),255);int np=0;char*tk=strtok(tmp,",");while(tk&&np<8){MASKS0[np++]=atoi(tk);tk=strtok(0,",");}}
 fprintf(stderr,"nF=%d masks0=%d,%d,%d,%d,%d,%d,%d,%d\n",nF,MASKS0[0],MASKS0[1],MASKS0[2],MASKS0[3],MASKS0[4],MASKS0[5],MASKS0[6],MASKS0[7]);
 if(wildcard){
  unsigned allowed[94];int av[64];
  for(int i=0;i<nF;i++)av[i]=base_prog[Faddr[i]];
  derive_allowed(av,1,allowed);
  int bits=0;for(int r=0;r<94;r++)bits+=__builtin_popcount(allowed[r]);
  int sc=eval_dp(MASKS0,allowed,NULL,NULL);
  /* per-input reach under this alphabet, ignoring sharing */
  int poss=0;int deadlist[256],nd=0;
  for(int b=0;b<256;b++){
   unsigned al=allowed[(OFFSET+3*b+5)%94];int any=0;
   for(int s=0;s<4096&&!any;s++){
    for(int p=0;p<8&&!any;p++){
     int a=fastcircuit(MASKS0,3*b+243,vals[b][0][s/512],vals[b][1][s/64%8],vals[b][2][s/8%8],vals[b][3][s%8],vals[b][4][p]);
     for(int j=0;j<8&&!any;j++)if(al&(1u<<j)){
      int aa=fastcr(a,vals[b][5][j]);
      for(int k=0;k<8;k++)if((fastcr(aa,vals[b][6][k])&255)==(b^81)){any=1;break;}
     }
    }
   }
   poss+=any;if(!any)deadlist[nd++]=b;
  }
  printf("{\"mode\":\"wildcard-upper-bound\",\"bits\":%d,\"dp\":%d,\"reach\":%d,\"dead\":[",bits,sc,poss);
  for(int i=0;i<nd;i++)printf("%s%d",i?",":"",deadlist[i]);
  printf("]}\n");
  return 0;
 }
 char fn[512];snprintf(fn,sizeof fn,"%s/rt_hi.jsonl",outdir);loghi=fopen(fn,"a");
 pthread_t th[64];targ_t ta[64];
 for(int i=0;i<nthreads;i++){ta[i].seed=0x243F6A8885A308D3UL*(i+3)^time(NULL);ta[i].tid=i;pthread_create(&th[i],NULL,worker,&ta[i]);}
 for(int i=0;i<nthreads;i++)pthread_join(th[i],NULL);
 return 0;
}
