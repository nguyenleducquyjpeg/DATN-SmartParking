// Shared Firebase schema with dashboard.html and dashboard_parking.py.
// Requires ArduinoJson 6.x or 7.x. This is a desktop prototype, not an industrial barrier.
#include <ArduinoJson.h>
#include <time.h>
#include <esp_system.h>

String eventKey() { return String((uint32_t)time(nullptr))+"_"+String(esp_random(),HEX); }

bool readLogisticsJson(String path, JsonDocument &doc) {
  if (WiFi.status()!=WL_CONNECTED) return false;
  HTTPClient http;
  http.begin(secureClient,String(DATABASE_URL_BASE)+path+".json");
  int code=http.GET();String body=http.getString();http.end();
  return code==200 && !deserializeJson(doc,body);
}

bool writeLogisticsJson(String path, JsonDocument &doc, bool patch=false) {
  if (WiFi.status()!=WL_CONNECTED) return false;
  String body;serializeJson(doc,body);
  HTTPClient http;http.begin(secureClient,String(DATABASE_URL_BASE)+path+".json");
  http.addHeader("Content-Type","application/json");
  int code=patch?http.sendRequest("PATCH",body):http.PUT(body);http.end();
  return code>=200 && code<300;
}

void fillEvent(JsonObject obj, JsonObject person, String uid, String plate, String lane, String kind, String reason) {
  obj["timestamp"][".sv"]="timestamp";
  obj["maNhanVien"]=person["maNhanVien"] | "";
  obj["hoTen"]=person["hoTen"] | "";
  obj["rfid"]=uid;obj["bienSo"]=plate;obj["huong"]=lane;
  obj["loai"]=kind;obj["lyDo"]=reason;
}

// Per-lane telemetry. scanId prevents a late result being shown for another card.
void publishGateStatus(String lane, String uid, String scanId, int &sequence,
                       String state, String reason="", String requestId="", float adc=-1, int limit=0) {
  DynamicJsonDocument status(1024);
  status["scanId"]=scanId;status["rfid"]=uid;status["huong"]=lane;
  status["sequence"]=++sequence;status["trangThai"]=state;status["lyDo"]=reason;
  status["timestamp"][".sv"]="timestamp";status["requestId"]=requestId;
  if(adc>=0)status["adc"]=adc;
  if(limit>0)status["nguongADC"]=limit;
  writeLogisticsJson("/TrangThaiCong/"+lane,status);
}

void handleEmployeeCard(String uid, String lane) {
  String scanId=eventKey();int phaseSequence=0;
  float measuredADC=-1;int measuredLimit=0;
  DynamicJsonDocument scan(512);
  scan["rfid"]=uid;scan["huong"]=lane;scan["eventId"]=scanId;
  scan["timestamp"][".sv"]="timestamp";
  if (!writeLogisticsJson("/SuKienRFID/"+lane,scan)) {showMessage("DATABASE ERROR","GATE CLOSED");return;}
  publishGateStatus(lane,uid,scanId,phaseSequence,"WAIT_CAMERA");

  DynamicJsonDocument catalogue(32768), waiting(2048), insideDoc(128), config(2048);
  String waitingPath=lane=="IN"?"/XeDangVao":"/XeDangRa";
  String reason="", plate="";
  if (!readLogisticsJson("/HoSoNhanVien",catalogue)) reason="PROFILE_READ_ERROR";
  String employeeId=catalogue["theRFID"][uid] | "";
  JsonObject person=catalogue["nhanVien"][employeeId].as<JsonObject>();
  if (reason=="" && (person.isNull() || employeeId=="")) reason="UNREGISTERED_CARD";
  if (reason=="" && !(person["hoatDong"] | false)) reason="INACTIVE_EMPLOYEE";
  // Allow card-first operation: PC continues OCR while this device waits.
  // A waiting record alone never grants access; all checks below still apply.
  if (reason=="") {
    showMessage("CARD RECEIVED",employeeId,"WAIT FOR CAMERA");
    unsigned long started=millis();bool matched=false;
    do {
      waiting.clear();
      if (readLogisticsJson(waitingPath,waiting)) {
        double cameraStamp=waiting["timestamp"] | 0.0;
        double age=(double)time(nullptr)*1000.0-cameraStamp;
        matched=String(waiting["rfid"] | "")==uid &&
                String(waiting["bienSo"] | "")==String(person["bienSo"] | "") &&
                cameraStamp>0 && age>=-5000 && age<=90000;
      }
      if(matched)break;
      delay(300);
    } while(millis()-started<15000);
    if(!matched)reason="CAMERA_NOT_MATCHED";
  }
  plate=waiting["bienSo"] | "";
  double stamp=waiting["timestamp"] | 0.0;
  double nowMs=(double)time(nullptr)*1000.0;
  String requestId=waiting["requestId"] | "";
  if (reason=="" && (nowMs<1700000000000.0 || stamp<=0 || nowMs-stamp>90000 || stamp-nowMs>5000 || requestId=="")) reason="CAMERA_SESSION_EXPIRED";
  if (reason=="" && (String(person["rfid"] | "")!=uid || String(person["bienSo"] | "")!=plate || String(waiting["rfid"] | "")!=uid)) reason="CARD_PLATE_MISMATCH";
  if (reason=="" && !readLogisticsJson("/XeTrongBai/"+uid,insideDoc)) reason="STATE_READ_ERROR";
  bool inside=insideDoc.as<bool>();
  if (reason=="" && inside!=(lane=="OUT")) reason="INVALID_VEHICLE_STATE";
  if (reason=="" && !readLogisticsJson("/CauHinh",config)) reason="CONFIG_READ_ERROR";
  int capacity=config["TongCho"] | 0;
  int freeSlots=config["ChoTrong"] | -1;
  if (reason=="" && (freeSlots<0 || capacity<=0 || freeSlots>capacity)) reason="INVALID_CAPACITY";
  if (reason=="" && lane=="IN" && freeSlots==0) reason="PARKING_FULL";
  if (reason!="") {
    DynamicJsonDocument denied(1024);fillEvent(denied.to<JsonObject>(),person,uid,plate,lane,"DENIED",reason);
    writeLogisticsJson("/NhatKyNhanVien/"+eventKey(),denied);
    publishGateStatus(lane,uid,scanId,phaseSequence,"DENIED",reason,requestId);
    showMessage("ACCESS DENIED",reason);return;
  }

  if (lane=="OUT") {
    // Separate ADC setting: do not reuse the legacy, linearly mapped NguongCon.
    int limit=config["NguongADC"] | 0;
    if (limit<=0 || limit>=4095) {
      publishGateStatus(lane,uid,scanId,phaseSequence,"ERROR","ADC_NOT_CONFIGURED",requestId);
      showMessage("SET ADC THRESHOLD","ON WEB FIRST");return;
    }
    publishGateStatus(lane,uid,scanId,phaseSequence,"TESTING","",requestId,-1,limit);
    showMessage("ALCOHOL TEST", "PLEASE BLOW", "RAW ADC ONLY");
    delay(2000);
    float sum=0;bool valid=true;
    for (int i=0;i<150;i++) {int raw=analogRead(sensor_pin);if(raw<=0||raw>=4095)valid=false;sum+=raw;delay(20);}
    float adc=sum/150.0;
    measuredADC=adc;measuredLimit=limit;
    String result=!valid?"ERROR":(adc>=limit?"FAIL":"PASS");
    DynamicJsonDocument test(1024);
    fillEvent(test.to<JsonObject>(),person,uid,plate,lane,result,"RAW_ADC_UNCALIBRATED");
    test["adc"]=adc;test["nguongADC"]=limit;test["requestId"]=requestId;
    if (!writeLogisticsJson("/NhatKyNhanVien/"+eventKey(),test)) {
      publishGateStatus(lane,uid,scanId,phaseSequence,"ERROR","SAVE_TEST_FAILED",requestId,adc,limit);
      showMessage("SAVE TEST FAILED","GATE CLOSED");return;
    }
    publishGateStatus(lane,uid,scanId,phaseSequence,result,"RAW_ADC_UNCALIBRATED",requestId,adc,limit);
    if(result!="PASS") {showMessage("EXIT DENIED",result,"ADC: "+String(adc,1));digitalWrite(led_pin,HIGH);delay(1500);digitalWrite(led_pin,LOW);return;}
  }

  // Recheck active assignment after measuring; a web update must revoke this attempt.
  DynamicJsonDocument fresh(2048);
  if (!readLogisticsJson("/HoSoNhanVien/nhanVien/"+employeeId,fresh) ||
      !(fresh["hoatDong"] | false) || String(fresh["rfid"] | "")!=uid || String(fresh["bienSo"] | "")!=plate) {
    publishGateStatus(lane,uid,scanId,phaseSequence,"DENIED","PROFILE_CHANGED",requestId,measuredADC,measuredLimit);
    showMessage("PROFILE CHANGED","SCAN AGAIN");return;
  }
  // One atomic multi-location update: current state, legacy compatibility and history.
  DynamicJsonDocument changes(4096);
  if(lane=="IN") changes["XeTrongBai/"+uid]=true;
  else changes["XeTrongBai/"+uid]=nullptr;
  changes["CauHinh/ChoTrong"]=lane=="IN"?freeSlots-1:min(capacity,freeSlots+1);
  JsonObject current=changes.createNestedObject("BienSoXe/"+uid);
  current["bienSo"]=plate;current["rfid"]=uid;current["maNhanVien"]=employeeId;
  current["hoTen"]=person["hoTen"];current["trangThai"]=lane;
  current["timestamp"][".sv"]="timestamp";
  JsonObject history=changes.createNestedObject("NhatKyNhanVien/"+eventKey());
  fillEvent(history,person,uid,plate,lane,lane,"GATE_COMMAND_ACCEPTED_NO_PASSAGE_SENSOR");
  history["requestId"]=requestId;
  if (!writeLogisticsJson("/",changes,true)) {
    publishGateStatus(lane,uid,scanId,phaseSequence,"ERROR","SAVE_STATE_FAILED",requestId,measuredADC,measuredLimit);
    showMessage("SAVE STATE FAILED","GATE CLOSED");return;
  }
  availableSlots=lane=="IN"?freeSlots-1:min(capacity,freeSlots+1);
  showMessage("ACCESS ALLOWED",employeeId,plate);
  if(lane=="IN")servoIn.write(GATE_OPEN);else servoOut.write(GATE_OPEN);
  publishGateStatus(lane,uid,scanId,phaseSequence,"OPENED","",requestId,measuredADC,measuredLimit);
  delay(4000);
  if(lane=="IN" && !isGateInEmergencyOpen)servoIn.write(GATE_CLOSED);
  if(lane=="OUT" && !isGateOutEmergencyOpen)servoOut.write(GATE_CLOSED);
  if((lane=="IN" && !isGateInEmergencyOpen)||(lane=="OUT" && !isGateOutEmergencyOpen))
    publishGateStatus(lane,uid,scanId,phaseSequence,"CLOSED","",requestId,measuredADC,measuredLimit);
}
