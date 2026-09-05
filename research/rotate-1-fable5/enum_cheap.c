/* Fixed structure: acc=rotr^j0(b); rot; crz(c1); swp(c2); rot; rot; rot; finb
 * (and the no-lead-rot variant), c1 in {bytes, rotr^1(bytes)}, c2 with
 * rotl(c2) in the same set. Exact 256-eval per combo. Reports top scores. */
#include <stdio.h>
static int ct[3][3] = {{1,0,0},{1,0,2},{2,2,1}};
static unsigned crazy(unsigned a, unsigned d){unsigned r=0,f=1;for(int i=0;i<10;i++){r+=(unsigned)ct[d%3][a%3]*f;a/=3;d/=3;f*=3;}return r;}
static unsigned rotr(unsigned w){return w/3+(w%3)*19683u;}
int main(void){
  unsigned cs[188]; int nc=0;
  for(int v=33;v<=126;v++){cs[nc++]=(unsigned)v; cs[nc++]=rotr((unsigned)v);}
  int best=-1;
  for(int j0=1;j0<=9;j0++)
  for(int lead=0;lead<=3;lead++)
  for(int tail=0;tail<=4;tail++)
  for(int i1=0;i1<nc;i1++)
  for(int i2=0;i2<nc;i2++){
    unsigned c1=cs[i1], c2s=cs[i2];           /* c2s = staged cell value */
    unsigned c2=rotr(c2s);                     /* A-load: rotr(stage) */
    int sc=0;
    for(int b=0;b<256;b++){
      unsigned acc=(unsigned)b;
      for(int j=0;j<j0;j++)acc=rotr(acc);
      for(int l=0;l<lead;l++)acc=rotr(acc);
      acc=crazy(acc,c1);
      acc=crazy(c2,acc);
      for(int t=0;t<tail;t++)acc=rotr(acc);
      acc=crazy(acc,(unsigned)b);
      if((int)(acc%256)==(((b<<1)|(b>>7))&0xFF))sc++;
    }
    if(sc>best){best=sc;
      printf("score %d j0=%d lead=%d tail=%d c1=%u c2stage=%u (c2=%u)\n",sc,j0,lead,tail,c1,c2s,c2);fflush(stdout);}
  }
  printf("BEST %d\n",best);
  return 0;
}
