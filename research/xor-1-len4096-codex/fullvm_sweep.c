/* Parallel exact whole-VM legal one-cell coordinate sweep. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <pthread.h>
#include <stdatomic.h>

#define M 59049
#define MAXN 4096
enum { JMP=4,OUT=5,IN=23,ROT=39,MOVD=40,CRZ=62,NOP=68,HLT=81 };
static const int CODES[8]={JMP,OUT,IN,ROT,MOVD,CRZ,NOP,HLT};
static const int CT[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static const char *XLAT2="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
static uint8_t base[MAXN],x2[128],bestprog[MAXN];
static uint16_t basefull[M];
typedef struct { int a,b,c; uint8_t va,vb,vc; } Job;
static Job *jobs; static int njobs;
static int N,nthreads=14,protects[32],np,best,best_a=-1,best_v=-1,best_b=-1,best_w=-1;
static int pairlo=-1,pairhi=-1;
static int crossalo=-1,crossahi=-1,crossblo=-1,crossbhi=-1;
static int triplelo=-1,triplehi=-1;
static const char *outpath;
static atomic_int nextjob;
static pthread_mutex_t mu=PTHREAD_MUTEX_INITIALIZER;

static int crazyw(int a,int d){int r=0,p=1;for(int i=0;i<10;i++){r+=CT[d%3][a%3]*p;a/=3;d/=3;p*=3;}return r;}
static int rotr(int w){return w/3+(w%3)*19683;}
static int byte_for(int code,int a){int v=(code-a)%94;if(v<0)v+=94;while(v<33)v+=94;return v;}
static int run(uint16_t *m,int b){
    int ua[8192],un=0;uint16_t uv[8192];
#define WR(X,V) do{if(un>=8192)goto bad;ua[un]=(X);uv[un]=m[(X)];un++;m[(X)]=(V);}while(0)
    int A=0,C=0,D=0,ins=0,on=0,ob=-1;
    for(int s=0;s<4096;s++){
        int w=m[C];if(w<33||w>126)goto bad;int op=(w+C)%94;
        if(op==HLT){int ok=on==1&&ob==(b^0x51);while(un){--un;m[ua[un]]=uv[un];}return ok;}
        if(op==JMP)C=m[D];
        else if(op==OUT){if(on++)goto bad;ob=A&255;}
        else if(op==IN){if(ins++)goto bad;A=b;}
        else if(op==ROT){int v=rotr(m[D]);WR(D,v);A=v;}
        else if(op==MOVD)D=m[D];
        else if(op==CRZ){int v=crazyw(A,m[D]);WR(D,v);A=v;}
        w=m[C];if(w<33||w>126)goto bad;WR(C,x2[w]);C=(C+1)%M;D=(D+1)%M;
    }
bad:while(un){--un;m[ua[un]]=uv[un];}return 0;
#undef WR
}
static int score(uint8_t *p,uint16_t *m,int *okp){
    memcpy(m,basefull,sizeof(basefull));
    for(int a=0;a<N;a++)m[a]=p[a];
    if(p[N-2]!=base[N-2]||p[N-1]!=base[N-1])
        for(int a=N;a<M;a++)m[a]=crazyw(m[a-1],m[a-2]);
    int s=0;uint8_t done[256]={0};*okp=1;
    for(int i=0;i<np;i++){int b=protects[i];if(done[b])continue;done[b]=1;int ok=run(m,b);s+=ok;if(!ok){*okp=0;return s;}}
    for(int b=0;b<256;b++)if(!done[b])s+=run(m,b);
    return s;
}
static void write_best(void){FILE*f=fopen(outpath,"wb");if(!f)exit(2);fwrite(bestprog,1,N,f);fclose(f);}
static void *worker(void *unused){(void)unused;uint8_t*p=malloc(MAXN);uint16_t*m=malloc(sizeof(uint16_t)*M);if(!p||!m)exit(2);
    for(;;){int j=atomic_fetch_add(&nextjob,1);int lim=jobs?njobs:N*8;if(j>=lim)break;
        int a,b=-1,c=-1,v,w=-1,u=-1;
        if(jobs){a=jobs[j].a;b=jobs[j].b;c=jobs[j].c;v=jobs[j].va;w=jobs[j].vb;u=jobs[j].vc;}
        else {int k=j%8;a=j/8;v=byte_for(CODES[k],a);if(v==base[a])continue;}
        memcpy(p,base,N);p[a]=(uint8_t)v;if(b>=0)p[b]=(uint8_t)w;if(c>=0)p[c]=(uint8_t)u;int pok=0,s=score(p,m,&pok);if(!pok)continue;
        pthread_mutex_lock(&mu);if(s>best){best=s;best_a=a;best_v=v;best_b=b;best_w=w;memcpy(bestprog,p,N);write_best();fprintf(stderr,"BEST %d/256 a=%d v=%d b=%d w=%d\n",s,a,v,b,w);}pthread_mutex_unlock(&mu);
    }free(p);free(m);return NULL;}
int main(int argc,char**argv){const char*seed=NULL;for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"-s")&&i+1<argc)seed=argv[++i];else if(!strcmp(argv[i],"-o")&&i+1<argc)outpath=argv[++i];
    else if(!strcmp(argv[i],"-j")&&i+1<argc)nthreads=atoi(argv[++i]);else if(!strcmp(argv[i],"-protect")&&i+1<argc&&np<32)protects[np++]=atoi(argv[++i]);
    else if(!strcmp(argv[i],"-pair-lo")&&i+1<argc)pairlo=atoi(argv[++i]);
    else if(!strcmp(argv[i],"-pair-hi")&&i+1<argc)pairhi=atoi(argv[++i]);
    else if(!strcmp(argv[i],"-cross-a-lo")&&i+1<argc)crossalo=atoi(argv[++i]);
    else if(!strcmp(argv[i],"-cross-a-hi")&&i+1<argc)crossahi=atoi(argv[++i]);
    else if(!strcmp(argv[i],"-cross-b-lo")&&i+1<argc)crossblo=atoi(argv[++i]);
    else if(!strcmp(argv[i],"-cross-b-hi")&&i+1<argc)crossbhi=atoi(argv[++i]);
    else if(!strcmp(argv[i],"-triple-lo")&&i+1<argc)triplelo=atoi(argv[++i]);
    else if(!strcmp(argv[i],"-triple-hi")&&i+1<argc)triplehi=atoi(argv[++i]);else return 2;}
    if(!seed||!outpath||nthreads<1||nthreads>64)return 2;FILE*f=fopen(seed,"rb");if(!f)return 2;N=(int)fread(base,1,MAXN,f);fclose(f);for(int v=33;v<=126;v++)x2[v]=(uint8_t)XLAT2[v-33];
    for(int a=0;a<N;a++)basefull[a]=base[a];for(int a=N;a<M;a++)basefull[a]=crazyw(basefull[a-1],basefull[a-2]);
    if(triplelo>=0||triplehi>=0){if(triplelo<0||triplehi<triplelo||triplehi>=N)return 2;int z=triplehi-triplelo+1;
        size_t cap=(size_t)z*(z-1)*(z-2)*343/6;jobs=malloc(sizeof(Job)*cap);if(!jobs)return 2;
        for(int a=triplelo;a<=triplehi;a++)for(int b=a+1;b<=triplehi;b++)for(int c=b+1;c<=triplehi;c++)for(int ka=0;ka<8;ka++){int va=byte_for(CODES[ka],a);if(va==base[a])continue;for(int kb=0;kb<8;kb++){int vb=byte_for(CODES[kb],b);if(vb==base[b])continue;for(int kc=0;kc<8;kc++){int vc=byte_for(CODES[kc],c);if(vc==base[c])continue;jobs[njobs++]=(Job){a,b,c,(uint8_t)va,(uint8_t)vb,(uint8_t)vc};}}}
    }
    if(pairlo>=0||pairhi>=0){if(jobs||pairlo<0||pairhi<pairlo||pairhi>=N)return 2;int w=pairhi-pairlo+1;
        jobs=malloc(sizeof(Job)*(size_t)w*(size_t)(w-1)*32);if(!jobs)return 2;
        for(int a=pairlo;a<=pairhi;a++)for(int b=a+1;b<=pairhi;b++)for(int ka=0;ka<8;ka++){int va=byte_for(CODES[ka],a);if(va==base[a])continue;
          for(int kb=0;kb<8;kb++){int vb=byte_for(CODES[kb],b);if(vb==base[b])continue;jobs[njobs++]=(Job){.a=a,.b=b,.c=-1,.va=(uint8_t)va,.vb=(uint8_t)vb};}}
    }
    if(crossalo>=0||crossahi>=0||crossblo>=0||crossbhi>=0){
        if(jobs||crossalo<0||crossahi<crossalo||crossblo<0||crossbhi<crossblo||crossbhi>=N)return 2;
        size_t cap=(size_t)(crossahi-crossalo+1)*(size_t)(crossbhi-crossblo+1)*64;
        jobs=malloc(sizeof(Job)*cap);if(!jobs)return 2;
        for(int a=crossalo;a<=crossahi;a++)for(int b=crossblo;b<=crossbhi;b++)if(a!=b)
          for(int ka=0;ka<8;ka++){int va=byte_for(CODES[ka],a);if(va==base[a])continue;
            for(int kb=0;kb<8;kb++){int vb=byte_for(CODES[kb],b);if(vb==base[b])continue;
              jobs[njobs++]=(Job){.a=a,.b=b,.c=-1,.va=(uint8_t)va,.vb=(uint8_t)vb};}}
    }
    uint16_t*m=malloc(sizeof(uint16_t)*M);int pok;best=score(base,m,&pok);free(m);memcpy(bestprog,base,N);write_best();fprintf(stderr,"baseline=%d protected=%d jobs=%d threads=%d\n",best,pok,jobs?njobs:N*8,nthreads);
    pthread_t th[64];for(int i=0;i<nthreads;i++)pthread_create(&th[i],NULL,worker,NULL);for(int i=0;i<nthreads;i++)pthread_join(th[i],NULL);
    fprintf(stderr,"final=%d best_a=%d best_v=%d best_b=%d best_w=%d\n",best,best_a,best_v,best_b,best_w);return 0;}
