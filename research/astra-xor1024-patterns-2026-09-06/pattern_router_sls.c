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
/* Binary witness: input byte, dependency count, then (source address, raw byte) pairs.
 * Only actual initial reads of mutable source cells are recorded. Fixed source,
 * input, and all listed bytes determine this successful diagnostic execution.
 */
static unsigned char pattern_free[128];static uint64_t pattern_deps[2];
static uint64_t pattern_seen[16][4096];static unsigned pattern_counts[16];static FILE *pattern_file;
static void record_pattern(int b){
 if(!pattern_file||pattern_counts[b]>=1024)return;
 uint64_t h=1469598103934665603ull;unsigned char record[258];int n=0;
 for(int a=0;a<128;a++)if(pattern_deps[a/64]&(1ull<<(a%64))){record[2+2*n]=a;record[3+2*n]=(unsigned char)base[a];n++;h=(h^a)*1099511628211ull;h=(h^base[a])*1099511628211ull;}
 if(!h)h=1;unsigned slot=(unsigned)h&4095;
 while(pattern_seen[b][slot]&&pattern_seen[b][slot]!=h)slot=(slot+1)&4095;
 if(pattern_seen[b][slot])return;pattern_seen[b][slot]=h;pattern_counts[b]++;
 record[0]=b;record[1]=n;fwrite(record,1,2+2*n,pattern_file);
}
static inline int fc(int a,int d){return t5[a%243][d%243]+243*t5[a/243][d/243];}
static inline int get(int a){if(stamp[a]==epoch)return work[a];if(a<128&&pattern_free[a])pattern_deps[a/64]|=1ull<<(a%64);return base[a];}
static inline void put(int a,int v){stamp[a]=epoch;work[a]=v;}
static int last_correct,last_halted,last_bits,lower_limit=41,target_input=-1,last_target;
static int score(void){
 int correct=0,halted=0,bits=0;last_target=0;
 for(int b=0;b<lower_limit;b++){
  epoch++;pattern_deps[0]=pattern_deps[1]=0;int a=0,c=0,d=0,reads=0,out=-1;
  for(int step=0;step<2048;step++){
   int w=get(c);if(w<33||w>126)break;int op=(w+c)%94;
   if(op==81){if(out>=0){halted++;bits+=8-__builtin_popcount((unsigned)(out^(b^81)));if(out==(b^81)){record_pattern(b);correct++;if(b==target_input)last_target=1;}}break;}
   if(op==4)c=get(d);
   else if(op==5){if(out!=-1)break;out=a&255;}
   else if(op==23){if(reads++)break;a=b;}
   else if(op==39){a=rot(get(d));put(d,a);}
   else if(op==40)d=get(d);
   else if(op==62){a=fc(a,get(d));put(d,a);}
   w=get(c);if(w<33||w>126)break;put(c,(unsigned char)enc[w-33]);c=(c+1)%59049;d=(d+1)%59049;
  }
 }
 last_correct=correct;last_halted=halted;last_bits=bits;return last_target*2000000+correct*100000+bits*10+halted;
}
static int root_value=88,depth_value=4;
static int post[128],isfree[128],used[128],nu;
static int route_valid(void){
 for(int i=0;i<nu;i++){int a=used[i];for(int k=0;k<depth_value;k++){if(a<0||a>=128)return 0;a=(isfree[a]?base[a]:post[a])+1;}if(a!=root_value)return 0;}return 1;
}
static uint64_t rng;static unsigned rnd(void){rng^=rng<<13;rng^=rng>>7;rng^=rng<<17;return (unsigned)rng;}
int main(int argc,char**argv){
 if(argc<7)return 2;if(argc>7)lower_limit=atoi(argv[7]);if(argc>8)root_value=atoi(argv[8]);if(argc>9)depth_value=atoi(argv[9]);if(argc>10)target_input=atoi(argv[10]);
 for(int a=0;a<243;a++)for(int d=0;d<243;d++)t5[a][d]=cv(a,d)%243;
 uint8_t p[2048];FILE*f=fopen(argv[1],"rb");int n=fread(p,1,sizeof p,f);fclose(f);for(int i=0;i<n;i++)base[i]=p[i];for(int i=n;i<59049;i++)base[i]=fc(base[i-1],base[i-2]);
 int nf,addr[128],nv[128],values[128][8],bestvalues[128];f=fopen(argv[2],"r");fscanf(f,"%d",&nf);for(int i=0;i<nf;i++){fscanf(f,"%d%d",&addr[i],&nv[i]);for(int j=0;j<nv[i];j++)fscanf(f,"%d",&values[i][j]);}fclose(f);
 f=fopen(argv[6],"r");for(int a=0;a<128;a++)fscanf(f,"%d",&post[a]);fscanf(f,"%d",&nu);for(int i=0;i<nu;i++)fscanf(f,"%d",&used[i]);fclose(f);for(int i=0;i<nf;i++)isfree[addr[i]]=1;if(!route_valid()){fprintf(stderr,"invalid baseline router\n");return 3;}
 for(int i=0;i<nf;i++)pattern_free[addr[i]]=1;if(argc>11)pattern_file=fopen(argv[11],"wb");
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
 for(int i=0;i<nf;i++)base[addr[i]]=bestvalues[i];score();
 printf("{\"event\":\"focused_complete\",\"target\":%d,\"target_passed\":%d,\"lower_correct\":%d,\"fitness\":%d}\n",target_input,last_target,last_correct,best);

 if(pattern_file){fclose(pattern_file);printf("{\"event\":\"patterns\",\"counts\":[");for(int b=0;b<16;b++)printf("%s%u",b?",":"",pattern_counts[b]);printf("]}\n");}

}
