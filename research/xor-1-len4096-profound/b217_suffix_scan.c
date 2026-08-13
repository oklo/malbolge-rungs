/* Enumerate all five-instruction suffixes after the shared 216/217 prefix.
 * The forced prefix at 2683..2686 is MOVD,ROT,CRZ,OUT: it is compatible with
 * input 217 and gives input 216 high-memory exits.  List every suffix that
 * completes input 217, so the 216 continuation search can test only genuine
 * compatibility candidates rather than all 7^5 possibilities.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
enum { M=59049,N=4096,JMP=4,OUT=5,IN=23,ROT=39,MOVD=40,CRZ=62,NOP=68,HLT=81 };
static const int OPS[7]={JMP,OUT,ROT,MOVD,CRZ,NOP,HLT};
static const int CT[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static const char X[]="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
static uint16_t fresh[M],pre[M],mem[M];
static int crazy(int a,int d){int r=0,p=1;for(int i=0;i<10;i++){r+=CT[(d/p)%3][(a/p)%3]*p;p*=3;}return r;}
static int rotr(int w){return w/3+(w%3)*19683;}
static int byte_for(int op,int a){int v=(op-a)%94;if(v<0)v+=94;while(v<33)v+=94;return v;}
static int step(int *A,int *C,int *D,int *used,int *on,int *ob,int input){
 int w=mem[*C];if(w<33||w>126)return 0;int op=(w+*C)%94;
 if(op==JMP)*C=mem[*D];else if(op==OUT){if((*on)++)return 0;*ob=*A&255;}
 else if(op==IN)*A=(*used)++?M-1:input;
 else if(op==ROT){mem[*D]=rotr(mem[*D]);*A=mem[*D];}
 else if(op==MOVD)*D=mem[*D];else if(op==CRZ){mem[*D]=crazy(*A,mem[*D]);*A=mem[*D];}
 else if(op==HLT)return -1;
 w=mem[*C];if(w<33||w>126)return 0;mem[*C]=(uint8_t)X[w-33];(*C)++;(*D)++;return 1;
}
int main(int ac,char **av){
 if(ac<2)return 2;FILE*f=fopen(av[1],"rb");if(!f)return 2;int n=fread(fresh,1,0,f);(void)n;fclose(f);
 f=fopen(av[1],"rb");int ch,i=0;while(i<N&&(ch=fgetc(f))!=EOF)fresh[i++]=(uint8_t)ch;fclose(f);for(;i<M;i++)fresh[i]=crazy(fresh[i-1],fresh[i-2]);
 memcpy(mem,fresh,sizeof mem);int A=0,C=0,D=0,used=0,on=0,ob=-1;
 while(C!=2683&&step(&A,&C,&D,&used,&on,&ob,217)>0){}if(C!=2683)return 2;memcpy(pre,mem,sizeof mem);
 const int prefix[4]={MOVD,ROT,CRZ,OUT};long count=0;
 for(long code=0;code<16807;code++){
  memcpy(mem,pre,sizeof mem);long z=code;for(int j=0;j<4;j++)mem[2683+j]=byte_for(prefix[j],2683+j);
  int so[5];for(int j=0;j<5;j++){so[j]=OPS[z%7];z/=7;mem[2687+j]=byte_for(so[j],2687+j);}
  int a=A,c=C,d=D,u=used,o=0,b=-1,r=1;for(int s=0;s<64&&r>0;s++)r=step(&a,&c,&d,&u,&o,&b,217);
  if(r<0&&o==1&&b==(217^0x51)){printf("suffix");for(int j=0;j<5;j++)printf(" %d",so[j]);putchar('\n');count++;}
 }
 fprintf(stderr,"b217 compatible suffixes=%ld\n",count);return 0;
}
