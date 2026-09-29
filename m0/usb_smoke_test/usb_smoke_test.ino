// M0: verify that the ESP32-C3 can run code and exchange USB serial messages.
// Keep the motor driver disconnected for this test.

char command[16];
size_t commandLength = 0;
unsigned long lastHeartbeat = 0;

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("M0 READY");
}

void loop() {
  while (Serial.available() > 0) {
    const char incoming = static_cast<char>(Serial.read());
    if (incoming == '\r') continue;

    if (incoming == '\n') {
      command[commandLength] = '\0';
      if (strcmp(command, "PING") == 0) {
        Serial.println("PONG");
      } else if (commandLength > 0) {
        Serial.println("UNKNOWN");
      }
      commandLength = 0;
    } else if (commandLength < sizeof(command) - 1) {
      command[commandLength++] = incoming;
    } else {
      commandLength = 0;
      Serial.println("TOO LONG");
    }
  }

  if (millis() - lastHeartbeat >= 1000) {
    lastHeartbeat = millis();
    Serial.println("M0 ALIVE");
  }
}
