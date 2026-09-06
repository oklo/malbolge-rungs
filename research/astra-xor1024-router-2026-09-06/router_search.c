/* Historical search: boundary-cell guard limitation documented in guard-audit.json.
 * The retained candidate is certified by native verification, not by this guard. */
/* GPT-6 Astra: optimize loader-legal router bytes that preserve upper-case routes.
 * Diagnostic native-semantics VM, single input read; Rust verification authoritative.
 */
#define main unused_table_main
#include "table_dp.c"
#undef main
#include <math.h>
#include <time.h>
static const char enc[]="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
static uint16_t t5[243][243],base[59049],work[59049];static unsigned stamp[59049],epoch;
static inline int fc(int a,int d){return t5[a%243][d%243]+243*t5[a/243][d/243];}
static inline int get(int a){return stamp[a]==epoch?work[a]:base[a];}
static inline void put(int a,int v){stamp[a]=epoch;work[a]=v;}
static int last_correct,last_halted,last_bits;
static int score(void){
 int correct=0,halted=0,bits=0;
 for(int b=0;b<41;b++){
  epoch++;int a=0,c=0,d=0,reads=0,out=-1;
  for(int step=0;step<2048;step++){
   int w=get(c);if(w<33||w>126)break;int op=(w+c)%94;
   if(op==81){if(out>=0){halted++;bits+=8-__builtin_popcount((unsigned)(out^(b^81)));if(out==(b^81))correct++;}break;}
   if(op==4)c=get(d);
   else if(op==5){if(out!=-1)break;out=a&255;}
   else if(op==23){if(reads++)break;a=b;}
   else if(op==39){a=rot(get(d));put(d,a);}
   else if(op==40)d=get(d);
   else if(op==62){a=fc(a,get(d));put(d,a);}
   w=get(c);if(w<33||w>126)break;put(c,(unsigned char)enc[w-33]);c=(c+1)%59049;d=(d+1)%59049;
  }
 }
 last_correct=correct;last_halted=halted;last_bits=bits;return correct*100000+bits*10+halted;
}
static int post[128],isfree[128],used[128],nu;
static int route_valid(void){
 for(int i=0;i<nu;i++){int a=used[i];for(int k=0;k<4;k++){if(a<0||a>=128)return 0;a=(isfree[a]?base[a]:post[a])+1;}if(a!=88)return 0;}return 1;
}
static uint64_t rng;static unsigned rnd(void){rng^=rng<<13;rng^=rng>>7;rng^=rng<<17;return (unsigned)rng;}
int main(int argc,char**argv){
 if(argc<6)return 2;
 for(int a=0;a<243;a++)for(int d=0;d<243;d++)t5[a][d]=cv(a,d)%243;
 uint8_t p[2048];FILE*f=fopen(argv[1],"rb");int n=fread(p,1,sizeof p,f);fclose(f);for(int i=0;i<n;i++)base[i]=p[i];for(int i=n;i<59049;i++)base[i]=fc(base[i-1],base[i-2]);
 int nf,addr[128],nv[128],values[128][8],bestvalues[128];f=fopen(argv[2],"r");fscanf(f,"%d",&nf);for(int i=0;i<nf;i++){fscanf(f,"%d%d",&addr[i],&nv[i]);for(int j=0;j<nv[i];j++)fscanf(f,"%d",&values[i][j]);}fclose(f);
 f=fopen(argv[6],"r");for(int a=0;a<128;a++)fscanf(f,"%d",&post[a]);fscanf(f,"%d",&nu);for(int i=0;i<nu;i++)fscanf(f,"%d",&used[i]);fclose(f);for(int i=0;i<nf;i++)isfree[addr[i]]=1;if(!route_valid()){fprintf(stderr,"invalid baseline router\n");return 3;}
 rng=strtoull(argv[3],0,10);int steps=atoi(argv[4]);int best=score();for(int i=0;i<nf;i++)bestvalues[i]=base[addr[i]];
 printf("{\"event\":\"baseline\",\"lower_correct\":%d,\"lower_halted\":%d,\"lower_bit_matches\":%d,\"mutable_router_cells\":%d}\n",last_correct,last_halted,last_bits,nf);fflush(stdout);
 for(int restart=0;restart<20;restart++){
  for(int i=0;i<nf;i++)base[addr[i]]=bestvalues[i];
  if(restart%5==4)for(int k=0;k<20;k++){int i=rnd()%nf,old=base[addr[i]];base[addr[i]]=values[i][rnd()%nv[i]];if(!route_valid())base[addr[i]]=old;}
  int sc=score();
  for(int it=0;it<steps;it++){
   int i=rnd()%nf,old=base[addr[i]];base[addr[i]]=values[i][rnd()%nv[i]];if(base[addr[i]]==old)continue;if(!route_valid()){base[addr[i]]=old;continue;}
   int ns=score();double frac=(double)it/steps,temp=300+120000*pow(1-frac,3);
   if(ns>=sc||(double)rnd()/4294967296.0<exp((ns-sc)/temp))sc=ns;else base[addr[i]]=old;
   if(sc>best){
    best=sc;for(int j=0;j<nf;j++)bestvalues[j]=base[addr[j]];
    for(int j=0;j<n;j++)p[j]=base[j];f=fopen(argv[5],"wb");fwrite(p,1,n,f);fclose(f);
    score();printf("{\"event\":\"improvement\",\"restart\":%d,\"iteration\":%d,\"lower_correct\":%d,\"lower_halted\":%d,\"lower_bit_matches\":%d,\"source_bytes\":%d}\n",restart,it,last_correct,last_halted,last_bits,n);fflush(stdout);
   }
  }
 }
}
