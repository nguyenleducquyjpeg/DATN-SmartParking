// Separate enrolment station: never flash this sketch onto the gate controller.
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>
#include <ArduinoJson.h>
#include <esp_system.h>
#include <time.h>
#if __has_include("station_config.h")
#include "station_config.h"
#else
#include "station_config.example.h"
#endif
#include "firebase_roots.h"
#include "card_payload.h"

MFRC522 reader(RFID_SS,RFID_RST);
MFRC522::MIFARE_Key cardKey;
WiFiClientSecure tls;
String bootId,basePath,jobEtag,lastSeenUid;
DynamicJsonDocument job(4096);
bool finishing=false;
unsigned long lastPoll=0,lastBeat=0,lastScan=0,lastReconnect=0;

double nowMs(){return (double)time(nullptr)*1000.0;}
bool clockReady(){return time(nullptr)>1700000000;}

int httpJson(const char* method,String path,JsonDocument& document,String* etag=nullptr,String expected=""){
  if(WiFi.status()!=WL_CONNECTED||!clockReady())return -1;
  HTTPClient http;
  String url=String(DATABASE_URL)+path+".json";
  if(strlen(DATABASE_AUTH_TOKEN))url+="?auth="+String(DATABASE_AUTH_TOKEN);
  http.setConnectTimeout(5000);http.setTimeout(7000);
  if(!http.begin(tls,url))return -1;
  const char* headers[]={"ETag"};http.collectHeaders(headers,1);
  if(etag)http.addHeader("X-Firebase-ETag","true");
  if(expected!="")http.addHeader("If-Match",expected);
  int status;
  if(String(method)=="GET"){
    status=http.GET();
    if(status==200){
      if(etag)*etag=http.header("ETag");
      String body=http.getString();document.clear();
      if(deserializeJson(document,body))status=-2;
    }
  }else{
    String body;serializeJson(document,body);http.addHeader("Content-Type","application/json");
    status=http.sendRequest(method,body);
  }
  http.end();return status;
}
bool put(String path,JsonDocument& document){int code=httpJson("PUT",path,document);return code>=200&&code<300;}

// Conditional status writes cannot replace a newer job from another browser.
bool saveJob(){
  DynamicJsonDocument current(4096);String tag;
  if(httpJson("GET",basePath+"/job",current,&tag)!=200)return false;
  if(String(current["id"]|"")!=String(job["id"]|""))return false;
  job["updatedAt"][".sv"]="timestamp";
  int result=httpJson("PUT",basePath+"/job",job,nullptr,tag);
  return result>=200&&result<300;
}
void finish(String state,String error=""){
  job["status"]=state;job["error"]=error;job["completedAt"][".sv"]="timestamp";
  finishing=true; // Retain result in RAM and retry network delivery; never rewrite the card.
}
bool releaseEraseLock(){
  if(String(job["operation"]|"")!="ERASE")return true;
  String path="/HoSoNhanVien/theThuHoi/"+String(job["rfid"]|"")+"/eraseJob",tag;
  DynamicJsonDocument value(256);
  if(httpJson("GET",path,value,&tag)!=200)return false;
  if(value.as<String>()!=String(job["id"]|""))return true;
  value.clear();return httpJson("PUT",path,value,nullptr,tag)==200;
}
void flushResult(){
  String id=job["id"]|"";
  if(!put(basePath+"/history/"+id,job))return;
  DynamicJsonDocument current(4096);String tag;
  if(httpJson("GET",basePath+"/job",current,&tag)!=200)return;
  if(String(current["id"]|"")!=id){if(releaseEraseLock())finishing=false;return;}
  if(saveJob()&&releaseEraseLock())finishing=false;
}
String uidText(){
  String uid;
  for(byte i=0;i<reader.uid.size;i++){if(reader.uid.uidByte[i]<16)uid+="0";uid+=String(reader.uid.uidByte[i],HEX);}
  uid.toUpperCase();return uid;
}
bool selectCard(){
  reader.PCD_StopCrypto1();
  byte atqa[2];byte length=2;
  auto result=reader.PICC_WakeupA(atqa,&length);
  return result==MFRC522::STATUS_OK && reader.PICC_ReadCardSerial();
}
void releaseCard(){reader.PICC_HaltA();reader.PCD_StopCrypto1();}
bool authenticate(byte block){
  byte trailer=(block/4)*4+3;
  return reader.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A,trailer,&cardKey,&reader.uid)==MFRC522::STATUS_OK;
}
bool readPayload(uint8_t* data){
  for(int i=0;i<6;i++){
    if(i==0||i==3)if(!authenticate(CARD_BLOCKS[i]))return false;
    byte buffer[18];byte length=18;
    if(reader.MIFARE_Read(CARD_BLOCKS[i],buffer,&length)!=MFRC522::STATUS_OK)return false;
    memcpy(data+i*16,buffer,16);
  }
  return true;
}
bool writeBlock(byte block,uint8_t* data){
  if(!authenticate(block))return false;
  return reader.MIFARE_Write(block,data,16)==MFRC522::STATUS_OK;
}
bool validId(String value,size_t maxLen){
  if(value.length()<1||value.length()>maxLen)return false;
  for(size_t i=0;i<value.length();i++)if(!((value[i]>='A'&&value[i]<='Z')||(value[i]>='0'&&value[i]<='9')||value[i]=='_'||value[i]=='-'))return false;
  return true;
}
bool profileMatches(JsonDocument& profile){
  return (profile["hoatDong"]|false) && String(profile["maNhanVien"]|"")==String(job["maNhanVien"]|"") &&
    String(profile["rfid"]|"")==String(job["rfid"]|"") && String(profile["bienSo"]|"")==String(job["bienSo"]|"") &&
    (profile["updatedAt"]|0.0)==(job["profileVersion"]|0.0);
}
bool eraseAllowed(){
  String uid=job["rfid"]|"";
  DynamicJsonDocument owner(256),record(2048);
  if(httpJson("GET","/HoSoNhanVien/theRFID/"+uid,owner)!=200||!owner.isNull())return false;
  if(httpJson("GET","/HoSoNhanVien/theThuHoi/"+uid,record)!=200)return false;
  return String(record["eraseJob"]|"")==String(job["id"]|"") &&
    (record["revokedAt"]|0.0)==(job["profileVersion"]|0.0);
}
void executeJob(String uid,MFRC522::PICC_Type type){
  if(uid!=String(job["rfid"]|"")){finish("ERROR","WRONG_CARD");return;}
  if(type!=MFRC522::PICC_TYPE_MIFARE_1K&&type!=MFRC522::PICC_TYPE_MIFARE_4K){finish("ERROR","UNSUPPORTED_CARD");return;}
  String employee=job["maNhanVien"]|"",plate=job["bienSo"]|"";
  String operation=job["operation"]|"WRITE";
  bool erase=operation=="ERASE";
  if(operation!="WRITE"&&!erase){finish("ERROR","INVALID_REQUEST");return;}
  uint8_t payload[PAYLOAD_SIZE],previous[PAYLOAD_SIZE],actual[PAYLOAD_SIZE];
  if(!validId(employee,40)||!validId(plate,10)||!makePayload(employee.c_str(),plate.c_str(),payload)){
    finish("ERROR","INVALID_REQUEST");return;
  }
  DynamicJsonDocument profile(2048);
  if(erase){
    if(!eraseAllowed()){finish("ERROR","PROFILE_CHANGED");return;}
    memset(payload,0,PAYLOAD_SIZE);
  }else{
    if(httpJson("GET","/HoSoNhanVien/nhanVien/"+employee,profile)!=200){finish("ERROR","PROFILE_READ_FAILED");return;}
    if(!profileMatches(profile)){finish("ERROR","PROFILE_CHANGED");return;}
  }
  // Re-select after network I/O; a swapped card must not receive any write.
  if(!selectCard()||uidText()!=uid){finish("ERROR","WRONG_CARD");return;}
  if(!readPayload(previous)){finish("ERROR","AUTH_READ_FAILED");return;}
  if(!canOverwrite(previous)){finish("ERROR","FOREIGN_DATA");return;}
  uint8_t pendingHeader[16];memcpy(pendingHeader,payload,16);memcpy(pendingHeader,"LGP1",4);
  // Write an incomplete marker first; commit the valid header only after other blocks.
  if(!writeBlock(CARD_BLOCKS[0],pendingHeader)){finish("ERROR","WRITE_FAILED");return;}
  for(int i=1;i<6;i++)if(!writeBlock(CARD_BLOCKS[i],payload+i*16)){finish("ERROR","WRITE_FAILED");return;}
  if(!writeBlock(CARD_BLOCKS[0],payload)){finish("ERROR","WRITE_FAILED");return;}
  releaseCard();
  job["status"]="VERIFYING";
  saveJob(); // Verification still runs even if telemetry cannot be delivered.
  if(!selectCard()||uidText()!=uid||!readPayload(actual)||memcmp(actual,payload,PAYLOAD_SIZE)){
    finish("ERROR","VERIFY_FAILED");return;
  }
  releaseCard();
  if(erase){if(!eraseAllowed()){finish("ERROR","PROFILE_CHANGED");return;}}
  else{
    if(httpJson("GET","/HoSoNhanVien/nhanVien/"+employee,profile)!=200){finish("ERROR","PROFILE_READ_FAILED");return;}
    if(!profileMatches(profile)){finish("ERROR","PROFILE_CHANGED");return;}
  }
  job["verified"]=true;job["format"]=erase?"EMPTY":"LGS1";job["bytesVerified"]=PAYLOAD_SIZE;
  finish("SUCCESS");
}
void setup(){
  Serial.begin(115200);
  SPI.begin(RFID_SCK,RFID_MISO,RFID_MOSI,RFID_SS);reader.PCD_Init();
  for(byte i=0;i<6;i++)cardKey.keyByte[i]=0xff;
  bootId=String(esp_random(),HEX)+String(esp_random(),HEX);
  basePath="/TramCapThe/"+String(STATION_ID);
  tls.setCACert(FIREBASE_ROOTS);
  WiFi.mode(WIFI_STA);WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
  configTime(0,0,"pool.ntp.org","time.google.com");
  Serial.println("Card writer ready. Set station_config.h; wait for WiFi/NTP.");
}
void loop(){
  if(WiFi.status()!=WL_CONNECTED){
    if(millis()-lastReconnect>10000){lastReconnect=millis();WiFi.reconnect();}
    delay(20);return;
  }
  if(!clockReady()){delay(20);return;}
  if(millis()-lastBeat>10000){
    lastBeat=millis();DynamicJsonDocument beat(512);
    beat["timestamp"][".sv"]="timestamp";beat["bootId"]=bootId;beat["firmware"]="card-writer-2";
    if(!put(basePath+"/heartbeat",beat))Serial.println("Heartbeat failed: check TLS/auth/network.");
  }
  if(millis()-lastPoll<1000){delay(20);return;}lastPoll=millis();
  if(finishing){flushResult();return;}
  if(httpJson("GET",basePath+"/job",job,&jobEtag)!=200)return;
  String state=job["status"]|"";
  if((state=="WRITING"||state=="VERIFYING")&&String(job["bootId"]|"")!=bootId){finish("ERROR","STATION_RESTARTED");flushResult();return;}
  if(state=="PENDING" && (job["expiresAt"]|0.0)<nowMs()){
    job["status"]="EXPIRED";job["error"]="EXPIRED";
    if(httpJson("PUT",basePath+"/job",job,nullptr,jobEtag)==200){finish("EXPIRED","EXPIRED");flushResult();}return;
  }
  if(!selectCard())return;
  String uid=uidText();auto type=reader.PICC_GetType(reader.uid.sak);
  if(uid!=lastSeenUid||millis()-lastScan>5000){
    lastSeenUid=uid;lastScan=millis();DynamicJsonDocument scan(512);
    scan["rfid"]=uid;scan["timestamp"][".sv"]="timestamp";
    scan["cardType"]=type==MFRC522::PICC_TYPE_MIFARE_1K?"MIFARE_1K":type==MFRC522::PICC_TYPE_MIFARE_4K?"MIFARE_4K":"UNSUPPORTED";
    put(basePath+"/scan",scan);
  }
  releaseCard();
  if(state!="PENDING")return;
  if((job["expiresAt"]|0.0)<nowMs())return; // Poll again to expire; never claim after deadline.
  String jobId=job["id"]|"";
  bool safeId=jobId.length()==36;
  for(size_t i=0;i<jobId.length();i++)if(!isxdigit(jobId[i])&&jobId[i]!='-')safeId=false;
  if(!safeId){job["status"]="ERROR";job["error"]="INVALID_REQUEST";saveJob();return;}
  job["status"]="WRITING";job["bootId"]=bootId;job["updatedAt"][".sv"]="timestamp";
  int claimed=httpJson("PUT",basePath+"/job",job,nullptr,jobEtag);
  if(claimed<200||claimed>=300)return;
  executeJob(uid,type);releaseCard();flushResult();
}
