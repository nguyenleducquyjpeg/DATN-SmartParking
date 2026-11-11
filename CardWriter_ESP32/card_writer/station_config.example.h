#pragma once
// Copy to station_config.h and enter the Wi-Fi credentials for this separate ESP32.
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* DATABASE_URL = "https://alcohol-detection-a3c5b-default-rtdb.asia-southeast1.firebasedatabase.app";
const char* STATION_ID = "CAP_THE_01";
// Optional current Firebase database auth token, according to existing database rules.
// Do not put a service-account JSON/private key here. Expired tokens must be refreshed.
const char* DATABASE_AUTH_TOKEN = "";
constexpr int RFID_SS = 5;
constexpr int RFID_RST = 27;
constexpr int RFID_SCK = 18;
constexpr int RFID_MISO = 19;
constexpr int RFID_MOSI = 23;
