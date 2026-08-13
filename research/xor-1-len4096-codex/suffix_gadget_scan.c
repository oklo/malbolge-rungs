/* Exact search of longer reset gadgets in one of the eight rotation cycles. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <pthread.h>
#include <stdatomic.h>
#define M 59049
#define MAXN 4096
#define MAXJ 20000000
#define MAXMV 10
enum { JMP=4,OUT=5,IN=23,ROT=39,MOVD=40,CRZ=62,NOP=68,HLT=81 };
static const int CT[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static const char *XLAT2="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
typedef struct { uint8_t nnop,nmv,which,node[MAXMV-1]; } Job;
static uint8_t base[MAXN],bestprog[MAXN],x2[128];static uint16_t basefull[M];
static Job *jobs;static int njobs,N,best=-1;static const char*outpath;static atomic_int nextjob;
static atomic_ullong maskcount[16];static pthread_mutex_t mu=PTHREAD_MUTEX_INITIALIZER;
static int crazyw(int a,int d){int r=0,p=1;for(int i=0;i<10;i++){r+=CT[d%3][a%3]*p;a/=3;d/=3;p*=3;}return r;}
static int rotr(int w){return w/3+(w%3)*19683;}
static int byte_for(int code,int a){int v=(code-a)%94;if(v<0)v+=94;while(v<33)v+=94;return v;}
static int legal_at(int v,int a){int op=(v+a)%94;return op==JMP||op==OUT||op==IN||op==ROT||op==MOVD||op==CRZ||op==NOP||op==HLT;}
static int forbidden(int q){static const int f[]={43,44,45,62,64,71,72,73,91,112};for(unsigned i=0;i<sizeof(f)/sizeof(f[0]);i++)if(q==f[i])return 1;return 0;}
static int run(uint16_t*m,int b){int ua[8192],un=0;uint16_t uv[8192];
#define WR(X,V) do{if(un>=8192)goto bad;ua[un]=(X);uv[un]=m[(X)];un++;m[(X)]=(V);}while(0)
 int A=0,C=0,D=0,ins=0,on=0,ob=-1;for(int s=0;s<4096;s++){int w=m[C];if(w<33||w>126)goto bad;int op=(w+C)%94;
  if(op==HLT){int ok=on==1&&ob==(b^0x51);while(un){--un;m[ua[un]]=uv[un];}return ok;}if(op==JMP)C=m[D];else if(op==OUT){if(on++)goto bad;ob=A&255;}else if(op==IN){if(ins++)goto bad;A=b;}else if(op==ROT){int v=rotr(m[D]);WR(D,v);A=v;}else if(op==MOVD)D=m[D];else if(op==CRZ){int v=crazyw(A,m[D]);WR(D,v);A=v;}w=m[C];if(w<33||w>126)goto bad;WR(C,x2[w]);C=(C+1)%M;D=(D+1)%M;}
bad:while(un){--un;m[ua[un]]=uv[un];}return 0;
#undef WR
}
static void build(uint8_t*p,const Job*j){memcpy(p,base,N);int old[39],ops[128],no=0;for(int a=0;a<39;a++)old[a]=(base[a]+a)%94;for(int a=0;a<12;a++)ops[no++]=old[a];
 for(int k=0;k<8;k++)if(k==j->which){for(int z=0;z<j->nnop;z++)ops[no++]=NOP;for(int z=0;z<j->nmv;z++)ops[no++]=MOVD;ops[no++]=ROT;}else{ops[no++]=MOVD;ops[no++]=MOVD;ops[no++]=ROT;}
 ops[no++]=MOVD;ops[no++]=MOVD;ops[no++]=JMP;int plen=37+j->nnop+j->nmv;if(no!=plen)exit(2);for(int a=0;a<plen;a++)p[a]=(uint8_t)byte_for(ops[a],a);
 int cur=73+j->nnop;for(int d=0;d<j->nmv-1;d++){p[cur]=(uint8_t)(j->node[d]-1);cur=j->node[d];}p[cur]=71;}
static void write_best(void){FILE*f=fopen(outpath,"wb");if(!f)exit(2);fwrite(bestprog,1,N,f);fclose(f);}
static void write_qualifier(const uint8_t*p,int i){char q[1024];snprintf(q,sizeof(q),"%s.q%d.mal",outpath,i);FILE*f=fopen(q,"wb");if(!f)exit(2);fwrite(p,1,N,f);fclose(f);}
static void *worker(void*x){(void)x;uint8_t*p=malloc(MAXN);uint16_t*m=malloc(sizeof(uint16_t)*M);if(!p||!m)exit(2);memcpy(m,basefull,sizeof(basefull));for(;;){int i=atomic_fetch_add(&nextjob,1);if(i>=njobs)break;Job*j=&jobs[i];build(p,j);int legal=1;for(int a=0;a<128;a++)if(!legal_at(p[a],a)){legal=0;break;}if(!legal)continue;for(int a=0;a<128;a++)m[a]=p[a];int mask=0;for(int b=0;b<4;b++)if(run(m,b))mask|=1<<b;atomic_fetch_add(&maskcount[mask],1);if(!(mask&1)||!(mask&10))continue;int s=0;for(int b=0;b<256;b++)s+=run(m,b);pthread_mutex_lock(&mu);write_qualifier(p,i);if(s>best){best=s;memcpy(bestprog,p,N);write_best();fprintf(stderr,"BEST %d/256 mask=%02x nnop=%d nmov=%d cycle=%d path=%d",s,mask,j->nnop,j->nmv,j->which,73+j->nnop);for(int d=0;d<j->nmv-1;d++)fprintf(stderr,",%d",j->node[d]);fprintf(stderr,",72\n");}pthread_mutex_unlock(&mu);}free(p);free(m);return NULL;}
static Job curjob;static uint8_t used[128];
static void gen_path(int depth,int source,int plen){if(depth==curjob.nmv-1){if(legal_at(71,source)){if(njobs>=MAXJ){fprintf(stderr,"job cap\n");exit(2);}jobs[njobs++]=curjob;}return;}for(int q=plen;q<=127;q++)if(!used[q]&&!forbidden(q)&&legal_at(q-1,source)){used[q]=1;curjob.node[depth]=(uint8_t)q;gen_path(depth+1,q,plen);used[q]=0;}}
int main(int ac,char**av){if(ac!=3)return 2;outpath=av[2];FILE*f=fopen(av[1],"rb");if(!f)return 2;N=(int)fread(base,1,MAXN,f);fclose(f);if(N<128)return 2;for(int v=33;v<=126;v++)x2[v]=(uint8_t)XLAT2[v-33];for(int a=0;a<N;a++)basefull[a]=base[a];for(int a=N;a<M;a++)basefull[a]=crazyw(basefull[a-1],basefull[a-2]);jobs=malloc(sizeof(Job)*MAXJ);if(!jobs)return 2;
 for(int z=0;z<=24;z++)for(int mv=2;mv<=MAXMV;mv++){int plen=37+z+mv,start=73+z;if(start<plen||start>127)continue;curjob.nnop=z;curjob.nmv=mv;used[start]=1;for(int w=0;w<8;w++){curjob.which=w;gen_path(0,start,plen);}used[start]=0;}
 fprintf(stderr,"jobs=%d threads=14\n",njobs);pthread_t th[14];for(int i=0;i<14;i++)pthread_create(&th[i],0,worker,0);for(int i=0;i<14;i++)pthread_join(th[i],0);for(int m=0;m<16;m++){unsigned long long n=atomic_load(&maskcount[m]);if(n)fprintf(stderr,"MASK %02x count=%llu\n",m,n);}fprintf(stderr,"final=%d\n",best);return 0;}
