#include <WiFiClientSecure.h>
#include <Wire.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <ESP32Servo.h>

// =====================================================
// OLED
// =====================================================
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

#define SDA_PIN 21
#define SCL_PIN 22

// =====================================================
// RFID
// =====================================================
#define SS_PIN_OUT 5
#define RST_PIN_OUT 27
MFRC522 rfid_out(SS_PIN_OUT, RST_PIN_OUT);

#define SS_PIN_IN 14
#define RST_PIN_IN 26
MFRC522 rfid_in(SS_PIN_IN, RST_PIN_IN);

// =====================================================
// SERVO
// =====================================================
#define SERVO_IN_PIN 25
#define SERVO_OUT_PIN 13

Servo servoIn;
Servo servoOut;

const int GATE_CLOSED = 0;
const int GATE_OPEN = 90;

// =====================================================
// SENSOR
// =====================================================
#define sensor_pin 32
#define led_pin 4

// =====================================================
// FIREBASE
// =====================================================
#define DATABASE_URL_BASE \
"https://alcohol-detection-a3c5b-default-rtdb.asia-southeast1.firebasedatabase.app"

#if __has_include("wifi_config.h")
#include "wifi_config.h"
#else
#include "wifi_config.example.h"
#endif

// Node mới: lưu các thẻ đang có xe trong bãi
#define INSIDE_NODE "/XeTrongBai/"

// =====================================================
// BIẾN
// =====================================================
float adcValue = 0;
float mgL = 0;

int threshold = 200;
int totalSlots = 50;
int availableSlots = 50;

unsigned long lastUpdateThreshold = 0;
const unsigned long updateInterval = 30000;

unsigned long lastCheckEmergency = 0;
const unsigned long emergencyInterval = 10000;

unsigned long lastOledUpdate = 0;

bool isGateInEmergencyOpen = false;
bool isGateOutEmergencyOpen = false;

WiFiClientSecure secureClient;

// =====================================================
// HIỂN THỊ THÔNG BÁO
// =====================================================
void showMessage(String line1, String line2 = "", String line3 = "") {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(5, 10);
  display.println(line1);

  if (line2.length() > 0) {
    display.setCursor(5, 28);
    display.println(line2);
  }

  if (line3.length() > 0) {
    display.setCursor(5, 46);
    display.println(line3);
  }

  display.display();
}

// =====================================================
// CẬP NHẬT SỐ CHỖ
// =====================================================
void updateSlotsToFirebase() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;

  String url =
    String(DATABASE_URL_BASE) +
    "/CauHinh/ChoTrong.json";

  http.begin(secureClient, url);
  http.addHeader("Content-Type", "application/json");

  int code = http.PUT(String(availableSlots));

  Serial.print("Firebase ChoTrong HTTP: ");
  Serial.println(code);

  http.end();
}

// =====================================================
// ĐỌC CẤU HÌNH FIREBASE
// =====================================================
void updateConfigFromFirebase() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String payload;

  // NguongCon
  http.begin(
    secureClient,
    String(DATABASE_URL_BASE) + "/CauHinh/NguongCon.json"
  );

  if (http.GET() == 200) {
    payload = http.getString();
    if (payload != "null" && payload.length() > 0)
      threshold = payload.toInt();
  }
  http.end();

  // TongCho
  http.begin(
    secureClient,
    String(DATABASE_URL_BASE) + "/CauHinh/TongCho.json"
  );

  if (http.GET() == 200) {
    payload = http.getString();
    if (payload != "null" && payload.length() > 0)
      totalSlots = payload.toInt();
  }
  http.end();

  // ChoTrong
  http.begin(
    secureClient,
    String(DATABASE_URL_BASE) + "/CauHinh/ChoTrong.json"
  );

  if (http.GET() == 200) {
    payload = http.getString();
    if (payload != "null" && payload.length() > 0)
      availableSlots = payload.toInt();
  }
  http.end();

  Serial.print("Nguong con: ");
  Serial.println(threshold);

  Serial.print("Tong cho: ");
  Serial.println(totalSlots);

  Serial.print("Cho trong: ");
  Serial.println(availableSlots);
}

// =====================================================
// EMERGENCY GATE
// =====================================================
void checkEmergencyGates() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;

  // IN
  http.begin(
    secureClient,
    String(DATABASE_URL_BASE) + "/CauHinh/MoCongInKhuan.json"
  );

  if (http.GET() == 200) {
    bool newState = (http.getString() == "true");

    if (newState != isGateInEmergencyOpen) {
      isGateInEmergencyOpen = newState;

      if (newState)
        servoIn.write(GATE_OPEN);
      else
        servoIn.write(GATE_CLOSED);
    }
  }
  http.end();

  // OUT
  http.begin(
    secureClient,
    String(DATABASE_URL_BASE) + "/CauHinh/MoCongOutKhuan.json"
  );

  if (http.GET() == 200) {
    bool newState = (http.getString() == "true");

    if (newState != isGateOutEmergencyOpen) {
      isGateOutEmergencyOpen = newState;

      if (newState)
        servoOut.write(GATE_OPEN);
      else
        servoOut.write(GATE_CLOSED);
    }
  }
  http.end();
}

// =====================================================
// KIỂM TRA THẺ BỊ KHÓA
// =====================================================
bool isCardLocked(String uid) {
  if (WiFi.status() != WL_CONNECTED) return false;

  HTTPClient http;

  String url =
    String(DATABASE_URL_BASE) +
    "/DanhSachDen/" +
    uid +
    ".json";

  http.begin(secureClient, url);

  int code = http.GET();
  String response = http.getString();

  http.end();

  return (code == 200 && response == "true");
}

// =====================================================
// MỞ KHÓA THẺ
// =====================================================
void unlockCardFirebase(String uid) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;

  String url =
    String(DATABASE_URL_BASE) +
    "/DanhSachDen/" +
    uid +
    ".json";

  http.begin(secureClient, url);
  http.sendRequest("DELETE");
  http.end();
}

// =====================================================
// KIỂM TRA UID ĐANG Ở TRONG BÃI
// =====================================================
bool isCarInside(String uid) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi mat ket noi - khong the kiem tra UID");
    return false;
  }

  HTTPClient http;

  String url =
    String(DATABASE_URL_BASE) +
    INSIDE_NODE +
    uid +
    ".json";

  http.begin(secureClient, url);

  int code = http.GET();
  String response = http.getString();

  http.end();

  Serial.print("Kiem tra XeTrongBai: ");
  Serial.print(code);
  Serial.print(" -> ");
  Serial.println(response);

  if (code == 200 && response == "true")
    return true;

  return false;
}

// =====================================================
// THÊM UID VÀO DANH SÁCH XE TRONG BÃI
// =====================================================
bool addCarInside(String uid) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi mat ket noi - khong luu duoc UID");
    return false;
  }

  HTTPClient http;

  String url =
    String(DATABASE_URL_BASE) +
    INSIDE_NODE +
    uid +
    ".json";

  http.begin(secureClient, url);
  http.addHeader("Content-Type", "application/json");

  int code = http.PUT("true");

  Serial.print("Them XeTrongBai: ");
  Serial.println(code);

  http.end();

  return (code == 200);
}

// =====================================================
// XÓA UID KHỎI DANH SÁCH XE TRONG BÃI
// =====================================================
bool removeCarInside(String uid) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi mat ket noi - khong xoa duoc UID");
    return false;
  }

  HTTPClient http;

  String url =
    String(DATABASE_URL_BASE) +
    INSIDE_NODE +
    uid +
    ".json";

  http.begin(secureClient, url);

  int code = http.sendRequest("DELETE");

  Serial.print("Xoa XeTrongBai: ");
  Serial.println(code);

  http.end();

  return (code == 200);
}

// =====================================================
// GIẢ LẬP CHỤP ẢNH
// =====================================================
void chupAnhGiaLap() {
  Serial.println();
  Serial.println("📸 Dang chup anh va day len Server...");
  Serial.println();
}

// =====================================================
// ĐỌC UID
// =====================================================
String readUID(MFRC522 &rfid) {
  String uid = "";

  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10)
      uid += "0";

    uid += String(rfid.uid.uidByte[i], HEX);
  }

  uid.toUpperCase();
  return uid;
}

// =====================================================
// SETUP
// =====================================================
#include "logistics_firebase.h"

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("======================================");
  Serial.println("      PARKING SYSTEM ESP32");
  Serial.println("======================================");

  SPI.begin();
  Wire.begin(SDA_PIN, SCL_PIN);

  // RFID
  rfid_out.PCD_Init();
  delay(100);
  rfid_in.PCD_Init();
  delay(100);

  Serial.println("RFID OUT OK");
  Serial.println("RFID IN OK");

  // Servo IN
  servoIn.setPeriodHertz(50);
  servoIn.attach(SERVO_IN_PIN, 500, 2400);
  servoIn.write(GATE_CLOSED);

  // Servo OUT
  servoOut.setPeriodHertz(50);
  servoOut.attach(SERVO_OUT_PIN, 500, 2400);
  servoOut.write(GATE_CLOSED);

  Serial.print("Servo IN  GPIO: ");
  Serial.println(SERVO_IN_PIN);

  Serial.print("Servo OUT GPIO: ");
  Serial.println(SERVO_OUT_PIN);

  // OLED
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("LOI OLED!");
    while (true) delay(100);
  }

  display.setTextColor(SSD1306_WHITE);

  // Sensor
  pinMode(sensor_pin, INPUT);
  pinMode(led_pin, OUTPUT);
  digitalWrite(led_pin, LOW);

  showMessage("Connecting WiFi...");

  // WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.println("Dang ket noi WiFi...");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi CONNECTED");

  // HTTPS
  secureClient.setInsecure();
  secureClient.setTimeout(5000);

  // UTC is required for camera session expiry.
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  analogReadResolution(12);
  // Firebase
  updateConfigFromFirebase();

  Serial.println();
  Serial.println("======================================");
  Serial.println("HE THONG SAN SANG");
  Serial.println("Servo IN  = GPIO25");
  Serial.println("Servo OUT = GPIO13");
  Serial.println("RFID IN   = SS GPIO14");
  Serial.println("RFID OUT  = SS GPIO5");
  Serial.println("======================================");
}

// =====================================================
// LOOP
// =====================================================
void loop() {
  unsigned long currentMillis = millis();

  // Emergency
  if (currentMillis - lastCheckEmergency >= emergencyInterval) {
    checkEmergencyGates();
    lastCheckEmergency = currentMillis;
  }

  // Cập nhật cấu hình
  if (currentMillis - lastUpdateThreshold >= updateInterval) {
    updateConfigFromFirebase();
    lastUpdateThreshold = currentMillis;
  }

  // OLED mặc định
  if (currentMillis - lastOledUpdate >= 1000) {
    display.clearDisplay();
    display.setTextSize(1);

    display.setCursor(15, 0);
    display.println("PARKING SYSTEM");

    display.setCursor(5, 15);
    display.print("Slots: ");
    display.print(availableSlots);
    display.print(" / ");
    display.println(totalSlots);

    display.setCursor(5, 35);
    display.println("IN: Scan Card Entry");

    display.setCursor(5, 50);
    display.println("OUT: Scan & Test BAC");

    display.display();

    lastOledUpdate = currentMillis;
  }

  // ===================================================
  // Employee profiles and logs share Firebase with the web dashboard.
  if (rfid_in.PICC_IsNewCardPresent() && rfid_in.PICC_ReadCardSerial()) {
    String uid=readUID(rfid_in);rfid_in.PICC_HaltA();rfid_in.PCD_StopCrypto1();
    handleEmployeeCard(uid,"IN");return;
  }
  if (rfid_out.PICC_IsNewCardPresent() && rfid_out.PICC_ReadCardSerial()) {
    String uid=readUID(rfid_out);rfid_out.PICC_HaltA();rfid_out.PCD_StopCrypto1();
    handleEmployeeCard(uid,"OUT");return;
  }
}
