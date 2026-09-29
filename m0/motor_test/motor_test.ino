// M0 first motor test for ESP32-C3 + ULN2003 + 28BYJ-48 (5 V).
// Upload with the motor driver disconnected. A test starts only after TEST\n.
// GPIO4/5/6/7 -> IN1/IN2/IN3/IN4. Motor power is separate from GPIO.

constexpr uint8_t kPins[4] = {4, 5, 6, 7};
constexpr uint16_t kTestSteps = 256;
constexpr uint32_t kStepIntervalMs = 6;
constexpr uint32_t kMaxRunMs = 1900;

char command[16];
uint8_t commandLength = 0;
bool running = false;
uint16_t stepsLeft = 0;
uint8_t phase = 0;
uint32_t nextStepAt = 0;
uint32_t startedAt = 0;

void coilsOff() {
  for (uint8_t i = 0; i < 4; ++i) digitalWrite(kPins[i], LOW);
}

void stopTest(const char* message) {
  coilsOff();
  running = false;
  stepsLeft = 0;
  Serial.println(message);
}

void handleCommand() {
  command[commandLength] = '\0';
  if (strcmp(command, "PING") == 0) {
    Serial.println("PONG");
  } else if (strcmp(command, "TEST") == 0) {
    coilsOff();
    phase = 0;
    stepsLeft = kTestSteps;
    startedAt = millis();
    nextStepAt = startedAt;
    running = true;
    Serial.println("TEST START");
  } else if (strcmp(command, "STOP") == 0) {
    stopTest("STOPPED");
  } else if (strcmp(command, "STATUS") == 0) {
    Serial.println(running ? "RUNNING" : "IDLE");
  } else if (commandLength > 0) {
    Serial.println("UNKNOWN");
  }
  commandLength = 0;
}

void setup() {
  for (uint8_t i = 0; i < 4; ++i) {
    digitalWrite(kPins[i], LOW);
    pinMode(kPins[i], OUTPUT);
  }
  coilsOff();
  Serial.begin(115200);
  delay(300);
  Serial.println("M0 MOTOR READY");
}

void loop() {
  while (Serial.available() > 0) {
    const char incoming = static_cast<char>(Serial.read());
    if (incoming == '\r') continue;
    if (incoming == '\n') {
      handleCommand();
    } else if (commandLength < sizeof(command) - 1) {
      command[commandLength++] = incoming;
    } else {
      commandLength = 0;
      Serial.println("TOO LONG");
    }
  }

  if (!running) return;
  const uint32_t now = millis();
  if (now - startedAt >= kMaxRunMs) {
    stopTest("TIMEOUT");
    return;
  }
  if (static_cast<int32_t>(now - nextStepAt) < 0) return;
  if (stepsLeft == 0) {
    stopTest("TEST DONE");
    return;
  }

  coilsOff();
  digitalWrite(kPins[phase], HIGH);  // One coil at a time for the USB test.
  phase = (phase + 1) & 3;
  --stepsLeft;
  nextStepAt += kStepIntervalMs;
}
