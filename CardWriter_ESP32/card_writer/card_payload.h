#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

// Only data blocks in sectors 1 and 2. Never write manufacturer/trailer blocks.
static const uint8_t CARD_BLOCKS[6]={4,5,6,8,9,10};
static const size_t PAYLOAD_SIZE=96;
inline uint32_t payloadCrc(const uint8_t* p,size_t n){
  uint32_t crc=0xffffffffU;
  for(size_t i=0;i<n;i++){crc^=p[i];for(int b=0;b<8;b++)crc=(crc>>1)^((crc&1)?0xedb88320U:0);}
  return ~crc;
}
inline bool makePayload(const char* employee,const char* plate,uint8_t* out){
  size_t a=strlen(employee),b=strlen(plate);
  if(a<1||a>40||b<7||b>10)return false;
  memset(out,0,PAYLOAD_SIZE);memcpy(out,"LGS1",4);
  out[4]=1;out[5]=(uint8_t)a;out[6]=(uint8_t)b;
  memcpy(out+8,employee,a);memcpy(out+48,plate,b);
  uint32_t crc=payloadCrc(out,92);
  for(int i=0;i<4;i++)out[92+i]=(crc>>(8*i))&255;
  return true;
}
inline bool canOverwrite(const uint8_t* old){
  if(!memcmp(old,"LGS1",4)||!memcmp(old,"LGP1",4))return true;
  for(size_t i=0;i<PAYLOAD_SIZE;i++)if(old[i]!=0&&old[i]!=255)return false;
  return true;
}
