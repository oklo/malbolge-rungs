/* Fable 5 run-4: instrumented two-level escape search.
 * scan mode: for input b, sample window combos, log which mutable low cells
 *   (5..127, non-pinned) failing escape runs read — the cells that gate them.
 * joint mode: enumerate window(b) x up to two gate cells' byte choices;
 *   any per-input hit is filtered by an exact all-256 model sweep, so a hit
 *   printed here is a full-program candidate scoring +1 (or more) globally.
 * usage: escape2 scan  <prog> <b> <samples>
 *        escape2 joint <prog> <b> <cell1[,cell2]> <out.mal>
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

static const int ops[8]={4,5,23,39,40,62,68,81};
static int ct[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static int cv(int a,int d){int v=0,p=1;for(int i=0;i<10;i++,p*=3){v+=ct[d%3][a%3]*p;a/=3;d/=3;}return v;}
static int rot_(int a){return a/3+a%3*19683;}
static int byte_(int op,int addr){int v=(op-addr)%94;if(v<0)v+=94;while(v<33)v+=94;return v;}
static const char enc[]="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
static uint16_t t5[243][243];
static inline int fastcr(int a,int d){return t5[a%243][d%243]+243*t5[a/243][d/243];}
static int OFFSET=244;
static uint8_t prog[2048]; static int n;
static uint16_t fill0[59049];
static uint16_t mem[59049]; static unsigned stamp[59049]; static unsigned epoch_;
static inline int get(int a){return stamp[a]==epoch_?mem[a]:fill0[a];}
static inline void put(int a,int v){stamp[a]=epoch_;mem[a]=v;}
static unsigned char readlog[128]; static int logging;

static int simulate(int b){
 epoch_++;
 int a=0,c=0,d=0,reads=0,out=-1,nout=0;
 for(int step=0;step<2048;step++){
  int w=get(c);if(w<33||w>126)return 0;
  int op=(w+c)%94;
  if(op==81)return nout==1&&out==(b^81);
  if(op==4){if(logging&&d<128)readlog[d]=1;c=get(d);}
  else if(op==5){out=a&255;nout++;if(nout>1)return 0;}
  else if(op==23){if(reads++)return 0;a=b;}
  else if(op==39){if(logging&&d<128)readlog[d]=1;a=rot_(get(d));put(d,a);}
  else if(op==40){if(logging&&d<128)readlog[d]=1;d=get(d);}
  else if(op==62){if(logging&&d<128)readlog[d]=1;a=fastcr(a,get(d));put(d,a);}
  w=get(c);if(w<33||w>126)return 0;
  put(c,(unsigned char)enc[w-33]);
  c=(c+1)%59049;d=(d+1)%59049;
 }
 return 0;
}

static int sweep256(void){
 int sc=0;
 for(int b=0;b<256;b++)sc+=simulate(b);
 return sc;
}

int main(int argc,char**argv){
 if(getenv("ESC_OFFSET"))OFFSET=atoi(getenv("ESC_OFFSET"));
 for(int x=0;x<243;x++)for(int y=0;y<243;y++)t5[x][y]=cv(x,y)%243;
 FILE*f=fopen(argv[2],"rb");n=fread(prog,1,sizeof prog,f);fclose(f);
 for(int i=0;i<n;i++)fill0[i]=prog[i];
 for(int i=n;i<59049;i++)fill0[i]=fastcr(fill0[i-1],fill0[i-2]);
 if(!strcmp(argv[1],"sweep")){
  int sc=0;printf("{\"fails\":[");int first=1;
  for(int bb=0;bb<256;bb++){if(simulate(bb))sc++;else{printf("%s%d",first?"":",",bb);first=0;}}
  printf("],\"score\":%d}\n",sc);return 0;
 }
 int b=atoi(argv[3]);
 int w0=OFFSET+3*b;
 int legal[7][8];
 for(int i=0;i<7;i++)for(int j=0;j<8;j++)legal[i][j]=byte_(ops[j],w0+i);
 if(!strcmp(argv[1],"scan")){
  long samples=atol(argv[4]);
  static long hist[128];unsigned long rng=88172645463325252UL;
  for(long s=0;s<samples;s++){
   rng^=rng<<13;rng^=rng>>7;rng^=rng<<17;
   unsigned long cc=rng;
   for(int i=0;i<7;i++){fill0[w0+i]=legal[i][cc&7];cc>>=3;}
   memset(readlog,0,sizeof readlog);logging=1;
   simulate(b);
   logging=0;
   for(int i=0;i<128;i++)if(readlog[i])hist[i]++;
  }
  printf("{\"b\":%d,\"cell_read_freq\":{",b);int first=1;
  for(int i=5;i<128;i++)if(hist[i]&&hist[i]<samples){printf("%s\"%d\":%ld",first?"":",",i,hist[i]);first=0;}
  printf("}}\n");
  return 0;
 }
 /* joint */
 int cells[2],nc=0;
 char*tok=strcmp(argv[4],"-")?strtok(argv[4],","):NULL;
 while(tok&&nc<2){cells[nc++]=atoi(tok);tok=strtok(0,",");}
 int clegal[2][8];
 for(int c=0;c<nc;c++)for(int j=0;j<8;j++)clegal[c][j]=byte_(ops[j],cells[c]);
 int base_sc;
 base_sc=sweep256();
 fprintf(stderr,"baseline all-256 model sweep: %d\n",base_sc);
 long total=2097152;for(int c=0;c<nc;c++)total*=8;
 int found=0;
 for(long code=0;code<total;code++){
  long cc=code;
  for(int i=0;i<7;i++){fill0[w0+i]=legal[i][cc&7];cc>>=3;}
  for(int c=0;c<nc;c++){fill0[cells[c]]=clegal[c][cc&7];cc>>=3;}
  if(!simulate(b))continue;
  int sc=sweep256();
  if(sc>base_sc){
   fprintf(stderr,"HIT b=%d sweep=%d\n",b,sc);
   printf("{\"b\":%d,\"sweep\":%d,\"w\":[",b,sc);
   for(int i=0;i<7;i++)printf("%s%d",i?",":"",fill0[w0+i]);
   printf("],\"cells\":{");
   for(int c=0;c<nc;c++)printf("%s\"%d\":%d",c?",":"",cells[c],(int)fill0[cells[c]]);
   printf("}}\n");fflush(stdout);
   if(sc==256||++found>=40){
    uint8_t out[2048];memcpy(out,prog,n);
    for(int i=0;i<7;i++)out[w0+i]=fill0[w0+i];
    for(int c=0;c<nc;c++)out[cells[c]]=fill0[cells[c]];
    f=fopen(argv[5],"wb");fwrite(out,1,n,f);fclose(f);
    if(sc==256){fprintf(stderr,"FULL 256 model sweep — wrote %s\n",argv[5]);return 0;}
   }
  }
 }
 fprintf(stderr,"joint done b=%d found=%d\n",b,found);
 return 0;
}
