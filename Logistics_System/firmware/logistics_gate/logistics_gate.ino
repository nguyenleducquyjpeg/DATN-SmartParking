// ESP32 prototype. Libraries: MFRC522, ESP32Servo, ArduinoJson (6 or 7).
// USB Serial JSON, 115200 baud. No Firebase credentials are embedded.
#include <SPI.h>
#include <MFRC522.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>
#include <esp_system.h>

MFRC522 readerIn(14, 26), readerOut(5, 27);
Servo gateIn, gateOut;
const int SENSOR_PIN=32, LED_PIN=4;
String line, token, direction, session;
unsigned long scannedAt=0, openedAt=0, sampleAt=0, testAt=0;
bool pending=false, opened=false, testing=false, measured=false, validSamples=true;
uint32_t sampleSum=0, samples=0;

void emit(const char* event, const char* message="") {
  StaticJsonDocument<384> doc;
  doc["event"]=event; doc["message"]=message; doc["sid"]=session;
  serializeJson(doc,Serial);Serial.println();
}

void scan(MFRC522 &reader, const char* lane) {
  if (!reader.PICC_IsNewCardPresent() || !reader.PICC_ReadCardSerial()) return;
  String uid;
  for (byte i=0;i<reader.uid.size;i++) {
    if (reader.uid.uidByte[i]<16) uid+="0";
    uid+=String(reader.uid.uidByte[i],HEX);
  }
  uid.toUpperCase();reader.PICC_HaltA();reader.PCD_StopCrypto1();
  token=String(esp_random(),HEX)+String(esp_random(),HEX);
  direction=lane;session="";pending=true;measured=false;testing=false;
  scannedAt=millis();digitalWrite(LED_PIN,LOW);
  StaticJsonDocument<384> doc;
  doc["event"]="CARD";doc["uid"]=uid;doc["direction"]=lane;doc["token"]=token;
  serializeJson(doc,Serial);Serial.println();
}

void command(String input) {
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc,input)) {emit("ERROR","Invalid JSON");return;}
  if (!pending || millis()-scannedAt>=90000 || opened) {emit("ERROR","Scan expired or consumed");return;}
  String cmd=doc["cmd"] | "";
  String incomingToken=doc["token"] | "";
  String sid=doc["sid"] | "";
  if (incomingToken!=token || sid.length()!=32) {emit("ERROR","Session/token mismatch");return;}
  if (cmd=="TEST") {
    if (direction!="OUT" || testing || measured) {emit("ERROR","Test already used or wrong lane");return;}
    session=sid;testing=true;testAt=millis();sampleAt=0;
    sampleSum=0;samples=0;validSamples=true;
  } else if (cmd=="OPEN") {
    if (testing || (direction=="OUT" && (!measured || !validSamples || sid!=session))) {
      emit("ERROR","No matching measurement");return;
    }
    session=sid;
    if (direction=="IN") gateIn.write(90); else gateOut.write(90);
    opened=true;openedAt=millis();pending=false;
    emit("OPENED");
  } else emit("ERROR","Unknown command");
}

void setup() {
  Serial.begin(115200);SPI.begin();
  readerIn.PCD_Init();readerOut.PCD_Init();
  gateIn.setPeriodHertz(50);gateOut.setPeriodHertz(50);
  gateIn.attach(25,500,2400);gateOut.attach(13,500,2400);
  gateIn.write(0);gateOut.write(0);
  pinMode(SENSOR_PIN,INPUT);pinMode(LED_PIN,OUTPUT);
  analogReadResolution(12);
  emit("READY","Logistics gate ready; raw ADC only");
}

void loop() {
  while (Serial.available()) {
    char c=Serial.read();
    if (c=='\n') {command(line);line="";}
    else if (c!='\r') {
      line+=c;
      if (line.length()>512) {line="";emit("ERROR","Command too long");}
    }
  }
  if (opened && millis()-openedAt>=4000) {
    gateIn.write(0);gateOut.write(0);opened=false;emit("CLOSED");
  }
  if (pending && millis()-scannedAt>=90000) {
    pending=false;testing=false;emit("ERROR","Scan expired; scan again");
  }
  if (testing) {
    if (millis()-sampleAt>=20) {
      sampleAt=millis();int adc=analogRead(SENSOR_PIN);
      if (adc<=0 || adc>=4095) validSamples=false;
      sampleSum+=adc;samples++;
    }
    if (millis()-testAt>=3000) {
      testing=false;measured=true;
      StaticJsonDocument<384> doc;
      doc["event"]="RESULT";doc["sid"]=session;
      doc["adc"]=samples ? (float)sampleSum/samples : 0;
      doc["valid"]=validSamples && samples>=100;
      doc["samples"]=samples;
      validSamples=validSamples && samples>=100;
      if (!validSamples) digitalWrite(LED_PIN,HIGH);
      serializeJson(doc,Serial);Serial.println();
    }
  }
  if (!opened && !testing) {scan(readerIn,"IN");scan(readerOut,"OUT");}
}
