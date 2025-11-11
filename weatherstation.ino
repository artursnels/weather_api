#include <WiFi.h>
#include "DHTStable.h"
#include <MQ135.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

DHTStable DHT;

#include <Adafruit_BMP085.h>


const char* ssid = "ssid";
const char* password = "psswd";

Adafruit_BMP085 bmp;

#define DHT22_PIN 4
#define RAIN_POWER_PIN 17
#define DO_PIN 16
#define PIN_ANEMOMETER 34
#define PIN_MQ135 32

int sensitivity = 200;

long MINUTE_INTERVAL = 5;



const float minVoltage = 0;  // Voltage corresponding to 0 m/s
const float maxVoltage = 5;  // Voltage corresponding to 32.4 m/s 
const float maxWindSpeed = 30; // Maximum wind speed in m/s





bool bmpOk = true;

float windspeedSum = 0;

void setup() {
    Serial.begin(115200);
      Wire.begin(21, 23);
      analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  pinMode(RAIN_POWER_PIN, OUTPUT);  
  pinMode(DO_PIN, INPUT);

    Serial.println("Initializing BMP180...");
    if (!bmp.begin()) {
        Serial.println("BMP180 not found!");
        bmpOk = false;
    } else {
        Serial.println("BMP180 detected successfully.");
    }

        if (!connectToWiFi(ssid, password)) {
          Serial.println("Could not establish a connection, aborting!");
          while (true) {
            delay(1000);
          }

        }

        Serial.println("\nConnected to the WiFi network");


}


unsigned long timeForUpload = 0;
unsigned long uploadInterval = MINUTE_INTERVAL*1000UL*60UL;

unsigned long timeForWindspeedMeasure = 0;
unsigned long windspeedInterval = 1000;


void loop() {

  if (millis() - timeForUpload >= uploadInterval) {
  WiFiClientSecure client;
  client.setInsecure();



    if (connectToWiFi(ssid, password)) {

      
      HTTPClient http;
      
      int attempts = 0;
      int humidity = int(getHumidity());
      while(humidity == -999 && attempts < 10) {
        humidity = int(getHumidity());
        attempts++;
        delay(50);
      }

      http.begin(client, "https://api.nelsons.lv/upload/");
      http.addHeader("Content-Type", "application/json");
      String json = "{\"token\": \"TOKEN\","
                "\"pressure_pa\": " + String(getPressure()) + ","
                "\"windspeed_ms\": " + String(windspeedSum/300.0) + ","
                "\"humidity_perc\": " + String(humidity) + ","
                "\"temperature_c\": " + String(getTemperatureC()) + ","
                "\"is_raining\": \"" + String(isRaining()) + "\","
                "\"air_quality\": \"" + String(getAirQuality()) + "\"}";
      int httpResponseCode = http.POST(json);
      
      Serial.println(httpResponseCode);
      Serial.println(http.getString());

      http.end();
      windspeedSum = 0;
      timeForUpload = millis();
    } 


  }

  if (millis() - timeForWindspeedMeasure >= windspeedInterval) {
    windspeedSum += getWindspeed();
    timeForWindspeedMeasure = millis();

  }

}



float getTemperatureC() {
  if (!bmpOk) {
    return -273;
  }
  return bmp.readTemperature();
}
int32_t getPressure() {
 if (!bmpOk) {
   return -1;
 }
 return bmp.readPressure(); 
}

float getHumidity() {
    uint32_t start = micros();
    int chk = DHT.read22(DHT22_PIN);
    uint32_t stop = micros();
    return DHT.getHumidity();
}


bool isRaining() {
digitalWrite(RAIN_POWER_PIN, HIGH);  // turn the rain sensor's power  ON
  delay(50);                      // wait 10 milliseconds

  int rain_state = digitalRead(DO_PIN);

  digitalWrite(RAIN_POWER_PIN, LOW);  // turn the rain sensor's power OFF
  return rain_state != HIGH;
}



float getWindspeed() {
  int adcValue = analogRead(PIN_ANEMOMETER);
  float voltage = (adcValue / 4095.00) * 3.3;
    Serial.println("VOLTAGE: " + String(voltage));
   if (voltage < minVoltage) {
    voltage = minVoltage;
  } else if (voltage > maxVoltage) {
    voltage = maxVoltage;
  }
  
  // Map the voltage to wind speed
  float windSpeed_mps = ((voltage - minVoltage) / (maxVoltage - minVoltage)) * maxWindSpeed;

  return windSpeed_mps;
}

float getPPM() {


int sensor_value = analogRead(PIN_MQ135);
int air_quality = sensor_value * sensitivity / 4095;

return air_quality;
}

String getAirQuality() {
  float ppm = getPPM();
    if (ppm <= 120) {
    return "good";
  } 
  else if (ppm <= 220) {
    return "moderate";
  } 
  else {
    return "bad";
  }


}


bool connectToWiFi(const char* ssid, const char* password) {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

   WiFi.begin(ssid, password);
    Serial.println("\nConnecting");
    int counter = 0;
    while(WiFi.status() != WL_CONNECTED){
        Serial.print(".");
        delay(100);
        counter++;
        if (counter >= 300) {
          return false;
        }
    }
  return true;
}
