/* Fable 5 run-4 schedule sweeper for L2.X1024.xor-1-len1024.
 * Exact overlap DP (from astra-xor1024-compact biased243_model.c) as the
 * objective, annealed over per-pass CRAZY/ROT/NOP mask schedules at 6..8
 * passes. first_free_input = 0 in this family, so the DP score covers all
 * 256 inputs; the native VM remains the judge of any assembled program.
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

static unsigned allowed[94];
static int tail5=62, tail6=62;
static int first_in, core, retlen, retops[64];
static uint8_t base_prog[2048]; static int base_len;
static uint16_t t5[243][243];
static inline int fastcr(int a,int d){return t5[a%243][d%243]+243*t5[a/243][d/243];}

/* per-input window byte alphabets, fixed by loader legality (offset 244) */
static int vals[256][7][8];
#define OFFSET 244

typedef struct { int masks[16]; int passes; } sched_t;

static inline int fastcircuit(const sched_t*S,int a,int m0,int m1,int m2,int m3,int m4){
 int m[5]={m0,m1,m2,m3,m4};
 for(int p=0;p<S->passes;p++)for(int i=0;i<5;i++)if(!(S->masks[p]&(1<<(i+5))))a=m[i]=(S->masks[p]&(1<<i))?rot_(m[i]):fastcr(a,m[i]);
 return a;
}

/* Exact DP. If table_out non-NULL, also reconstruct the optimal table. */
static int eval_sched(const sched_t*S, uint8_t *table_out, uint16_t (*prevbuf)[4096]){
 int dp[4096],next[4096];
 for(int s=0;s<4096;s++)dp[s]=0;
 for(int b=0;b<256;b++){
  for(int ns=0;ns<4096;ns++)next[ns]=-10000;
  unsigned al=allowed[(OFFSET+3*b+5)%94];
  for(int s=0;s<4096;s++){
   if(dp[s]<0)continue;
   for(int p=0;p<8;p++){
    int a=fastcircuit(S,3*b+243,vals[b][0][s/512],vals[b][1][s/64%8],vals[b][2][s/8%8],vals[b][3][s%8],vals[b][4][p]);
    for(int j=0;j<8;j++)if(al&(1u<<j)){
     int aa=tail5==62?fastcr(a,vals[b][5][j]):tail5==39?rot_(vals[b][5][j]):a;
     for(int k=0;k<8;k++){
      int w=(tail6==62?fastcr(aa,vals[b][6][k]):tail6==39?rot_(vals[b][6][k]):aa)&255,ok=w==(b^81),ns=((s%8)*64+p*8+j)*8+k;
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

static int assemble(const sched_t*S,const uint8_t*table,uint8_t*out){
 memcpy(out,base_prog,2048);
 memcpy(out+OFFSET,table,772);
 int end=core;
 for(int pass=0;pass<S->passes;pass++){
  if(pass){for(int j=0;j<retlen;j++){out[end]=byte_(retops[j],end);end++;}}
  for(int j=0;j<5;j++){int op=(S->masks[pass]&(1<<(j+5)))?68:(S->masks[pass]&(1<<j))?39:62;out[end]=byte_(op,end);end++;}
 }
 int tail[4]={tail5,tail6,5,81};for(int j=0;j<4;j++){out[end]=byte_(tail[j],end);end++;}
 if(end>OFFSET)return -1;
 return 1016;
}

static pthread_mutex_t lk=PTHREAD_MUTEX_INITIALIZER;
static int gbest=0; static long gevals=0;
static FILE *loghi;
static const char *outdir;

static unsigned long xs(unsigned long*s){*s^=*s<<13;*s^=*s>>7;*s^=*s<<17;return *s;}

static void report(const sched_t*S,int sc){
 pthread_mutex_lock(&lk);
 if(sc>=250){
  fprintf(loghi,"{\"score\":%d,\"passes\":%d,\"masks\":[",sc,S->passes);
  for(int i=0;i<S->passes;i++)fprintf(loghi,"%s%d",i?",":"",S->masks[i]);
  fprintf(loghi,"]}\n");fflush(loghi);
 }
 if(sc>gbest){
  gbest=sc;
  fprintf(stderr,"[best] score=%d passes=%d masks=",sc,S->passes);
  for(int i=0;i<S->passes;i++)fprintf(stderr,"%d,",S->masks[i]);
  fprintf(stderr," evals=%ld\n",gevals);
  /* durable: rebuild with table + program */
  static uint16_t (*pv)[4096]=NULL; if(!pv)pv=malloc(256*4096*2);
  uint8_t table[772],prog[2048];
  sched_t T=*S; eval_sched(&T,table,pv);
  if(assemble(&T,table,prog)==1016){
   char fn[512];snprintf(fn,sizeof fn,"%s/best_%d.mal",outdir,sc);
   FILE*f=fopen(fn,"wb");fwrite(prog,1,1016,f);fclose(f);
   snprintf(fn,sizeof fn,"%s/best_%d.masks",outdir,sc);
   f=fopen(fn,"w");fprintf(f,"%d ",T.passes);for(int i=0;i<T.passes;i++)fprintf(f,"%d,",T.masks[i]);fclose(f);
  }
 }
 gevals++;
 pthread_mutex_unlock(&lk);
}

typedef struct { unsigned long seed; int tid; } targ_t;

static void* worker(void*arg){
 targ_t*ta=arg; unsigned long rng=ta->seed;
 uint16_t (*pv)[4096]=NULL; /* no reconstruction in hot loop */
 /* seeds: retained schedules from the corpus */
 static const int seeds[][10]={
  {8,386,80,108,146,278,272,20,7,0},
  {8,3,20,21,18,19,24,16,7,0},
  {9,89,3,20,184,208,209,16,20,7},
  {8,3,16,60,146,23,272,20,7,0},
 };
 sched_t cur;
 int sn=xs(&rng)%4;
 cur.passes=seeds[sn][0]; if(cur.passes>8)cur.passes=8;
 for(int i=0;i<cur.passes;i++)cur.masks[i]=seeds[sn][1+i]&1023;
 int csc=eval_sched(&cur,NULL,pv); report(&cur,csc);
 double T0=3.0;
 long iter=0;
 sched_t best=cur; int bsc=csc;
 for(;;iter++){
  double T=T0*(0.5+0.5*(double)(xs(&rng)%1000)/1000.0);
  sched_t nxt=cur;
  int mv=xs(&rng)%100;
  if(mv<50){ /* flip 1-3 bits in one pass */
   int p=xs(&rng)%nxt.passes;
   int nb=1+xs(&rng)%3;
   for(int i=0;i<nb;i++)nxt.masks[p]^=1<<(xs(&rng)%10);
  } else if(mv<75){ /* randomize one pass */
   nxt.masks[xs(&rng)%nxt.passes]=xs(&rng)%1024;
  } else if(mv<85){ /* swap two passes */
   int a=xs(&rng)%nxt.passes,b=xs(&rng)%nxt.passes;
   int t=nxt.masks[a];nxt.masks[a]=nxt.masks[b];nxt.masks[b]=t;
  } else if(mv<93&&nxt.passes<8){ /* insert pass */
   int p=xs(&rng)%(nxt.passes+1);
   for(int i=nxt.passes;i>p;i--)nxt.masks[i]=nxt.masks[i-1];
   nxt.masks[p]=xs(&rng)%1024; nxt.passes++;
  } else if(nxt.passes>5){ /* delete pass */
   int p=xs(&rng)%nxt.passes;
   for(int i=p;i<nxt.passes-1;i++)nxt.masks[i]=nxt.masks[i+1];
   nxt.passes--;
  }
  int nsc=eval_sched(&nxt,NULL,pv);
  report(&nxt,nsc);
  if(nsc>=256){fprintf(stderr,"[SOLVE-CANDIDATE] thread %d\n",ta->tid);}
  if(nsc>=csc || (double)(xs(&rng)%10000)/10000.0 < exp((nsc-csc)/T)){cur=nxt;csc=nsc;}
  if(csc>bsc){best=cur;bsc=csc;}
  if(iter%400==399){ /* restart kick: return to best with a shake */
   cur=best;csc=bsc;
   for(int i=0;i<2;i++)cur.masks[xs(&rng)%cur.passes]^=1<<(xs(&rng)%10);
   csc=eval_sched(&cur,NULL,pv);
  }
 }
 return NULL;
}
#include <math.h>
int main(int argc,char**argv){
 outdir=argv[1];
 int nthreads=argc>2?atoi(argv[2]):8;
 /* load fixed inputs from the astra compact dir */
 const char*ad=getenv("SWEEP_AD")?getenv("SWEEP_AD"):"research/astra-xor1024-compact-2026-09-06";
 char fn[512];
 snprintf(fn,sizeof fn,"%s",getenv("SWEEP_ALLOWED")?getenv("SWEEP_ALLOWED"):"research/astra-xor1024-compact-2026-09-06/allowed.txt");
 FILE*f=fopen(fn,"r");for(int p=0;p<94;p++)fscanf(f,"%u",&allowed[p]);fclose(f);
 snprintf(fn,sizeof fn,"%s/model-config.txt",ad);
 f=fopen(fn,"r");fscanf(f,"%d%d%d",&first_in,&core,&retlen);for(int i=0;i<retlen;i++)fscanf(f,"%d",&retops[i]);fclose(f);
 snprintf(fn,sizeof fn,"%s/base.mal",ad);
 f=fopen(fn,"rb");base_len=fread(base_prog,1,2048,f);fclose(f);
 if(getenv("TAILOPS")){sscanf(getenv("TAILOPS"),"%d,%d",&tail5,&tail6);}
 for(int a=0;a<243;a++)for(int d=0;d<243;d++)t5[a][d]=cv(a,d)%243;
 for(int b=0;b<256;b++)for(int i=0;i<7;i++)for(int j=0;j<8;j++)vals[b][i][j]=byte_(ops[j],OFFSET+3*b+i);
 snprintf(fn,sizeof fn,"%s/hi.jsonl",outdir);
 loghi=fopen(fn,"a");
 if(getenv("SWEEP_ONESHOT")){
  sched_t S; S.passes=0;
  char tmp[256];strncpy(tmp,getenv("SWEEP_ONESHOT"),255);
  char*tk=strtok(tmp,",");while(tk&&S.passes<16){S.masks[S.passes++]=atoi(tk);tk=strtok(0,",");}
  int sc=eval_sched(&S,NULL,NULL);
  printf("{\"tail\":[%d,%d],\"score\":%d}\n",tail5,tail6,sc);
  return 0;
 }
 pthread_t th[64]; targ_t ta[64];
 for(int i=0;i<nthreads;i++){ta[i].seed=0x9e3779b97f4a7c15UL*(i+1)^time(NULL);ta[i].tid=i;pthread_create(&th[i],NULL,worker,&ta[i]);}
 for(int i=0;i<nthreads;i++)pthread_join(th[i],NULL);
 return 0;
}
