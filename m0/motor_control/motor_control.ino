// ESP32-C3 SuperMini + ULN2003 + 28BYJ-48 (5 V).
// GPIO4/5/6/7 -> IN1/IN2/IN3/IN4; board 5V/G -> driver +/-.
// Serial (115200): RUN LOW, RUN MEDIUM, RUN HIGH, RUN XHIGH,
// RUN ULTRA, TEST 1900, TEST 1800, TEST 1700, TEST FAST,
// TEST FAST20, STOP, STATUS, PING.
// TEST commands stop after 5 or 20 seconds.
// On the current 23 cm model, 1500 us lost steps and 1800 us paused briefly;
// keep normal RUN ULTRA at the proven 2000 us interval.
// The 1:32 / 20 ohm motor with white petals also failed to turn continuously
// at 1500 and 1800 us; do not promote those test intervals to RUN presets.
// Outputs are off at boot and after STOP or a 30-second command timeout.

constexpr uint8_t kPins[4] = {4, 5, 6, 7};
constexpr uint32_t kTimeoutMs = 30000;
constexpr uint32_t kFastTestMs = 5000;
constexpr uint32_t kFastTestLongMs = 20000;
constexpr uint8_t kMaxCommand = 31;

char command[kMaxCommand + 1];
uint8_t commandLength = 0;
uint8_t phase = 0;
uint8_t speed = 0; // 0=stopped, 1=low, 2=medium, 3=high, 4=xhigh, 5=ultra, 6=fast test
uint32_t targetIntervalUs = 0;
uint32_t currentIntervalUs = 0;
uint32_t nextStepAtUs = 0;
uint32_t lastRunCommandAt = 0;
uint32_t fastTestDurationMs = kFastTestMs;

void coilsOff() {
  for (uint8_t i = 0; i < 4; ++i) digitalWrite(kPins[i], LOW);
}

void stopMotor(const char* response) {
  speed = 0;
  coilsOff();
  Serial.println(response);
}

void runAt(uint8_t requestedSpeed, uint32_t intervalUs, const char* response) {
  lastRunCommandAt = millis();
  if (speed != requestedSpeed) {
    if (speed == 0) currentIntervalUs = 10000; // Start gently, then accelerate.
    speed = requestedSpeed;
    targetIntervalUs = intervalUs;
    nextStepAtUs = micros();
    Serial.println(response);
  }
}

void handleCommand() {
  command[commandLength] = '\0';
  if (strcmp(command, "PING") == 0) {
    Serial.println("PONG");
  } else if (strcmp(command, "RUN LOW") == 0) {
    runAt(1, 32000, "RUNNING LOW");
  } else if (strcmp(command, "RUN MEDIUM") == 0) {
    runAt(2, 16000, "RUNNING MEDIUM");
  } else if (strcmp(command, "RUN HIGH") == 0) {
    runAt(3, 8000, "RUNNING HIGH");
  } else if (strcmp(command, "RUN XHIGH") == 0) {
    runAt(4, 4000, "RUNNING XHIGH");
  } else if (strcmp(command, "RUN ULTRA") == 0) {
    runAt(5, 2000, "RUNNING ULTRA");
  } else if (strcmp(command, "TEST FAST") == 0) {
    stopMotor("TEST FAST START");
    fastTestDurationMs = kFastTestMs;
    runAt(6, 1500, "RUNNING FAST TEST");
  } else if (strcmp(command, "TEST FAST20") == 0) {
    stopMotor("TEST FAST20 START");
    fastTestDurationMs = kFastTestLongMs;
    runAt(6, 1500, "RUNNING FAST TEST");
  } else if (strcmp(command, "TEST 1900") == 0) {
    stopMotor("TEST 1900 START");
    fastTestDurationMs = kFastTestLongMs;
    runAt(6, 1900, "RUNNING 1900 TEST");
  } else if (strcmp(command, "TEST 1800") == 0) {
    stopMotor("TEST 1800 START");
    fastTestDurationMs = kFastTestLongMs;
    runAt(6, 1800, "RUNNING 1800 TEST");
  } else if (strcmp(command, "TEST 1700") == 0) {
    stopMotor("TEST 1700 START");
    fastTestDurationMs = kFastTestLongMs;
    runAt(6, 1700, "RUNNING 1700 TEST");
  } else if (strcmp(command, "STOP") == 0) {
    stopMotor("STOPPED");
  } else if (strcmp(command, "STATUS") == 0) {
    switch (speed) {
      case 1: Serial.println("RUNNING LOW"); break;
      case 2: Serial.println("RUNNING MEDIUM"); break;
      case 3: Serial.println("RUNNING HIGH"); break;
      case 4: Serial.println("RUNNING XHIGH"); break;
      case 5: Serial.println("RUNNING ULTRA"); break;
      case 6: Serial.println("RUNNING FAST TEST"); break;
      default: Serial.println("IDLE"); break;
    }
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
  Serial.println("M0 CONTROL READY");
}

void loop() {
  while (Serial.available() > 0) {
    const char incoming = static_cast<char>(Serial.read());
    if (incoming == '\r') continue;
    if (incoming == '\n') {
      handleCommand();
    } else if (commandLength < kMaxCommand) {
      command[commandLength++] = incoming;
    } else {
      commandLength = 0;
      Serial.println("TOO LONG");
    }
  }

  if (speed == 0) return;
  const uint32_t now = millis();
  if (speed == 6 && now - lastRunCommandAt >= fastTestDurationMs) {
    stopMotor("TEST FAST DONE");
    return;
  }
  if (now - lastRunCommandAt >= kTimeoutMs) {
    stopMotor("TIMEOUT");
    return;
  }
  const uint32_t nowUs = micros();
  if (static_cast<int32_t>(nowUs - nextStepAtUs) < 0) return;

  coilsOff();
  digitalWrite(kPins[phase], HIGH); // Same one-coil sequence as the successful short test.
  phase = (phase + 1) & 3;
  // Accelerate more gradually above HIGH; the attached logo adds inertia.
  if (currentIntervalUs > targetIntervalUs) {
    const uint32_t ramp = currentIntervalUs <= 4000
        ? max(2UL, currentIntervalUs / 1000)
        : max(10UL, currentIntervalUs / 100);
    currentIntervalUs = max(targetIntervalUs, currentIntervalUs - ramp);
  } else if (currentIntervalUs < targetIntervalUs) {
    const uint32_t ramp = max(10UL, currentIntervalUs / 100);
    currentIntervalUs = min(targetIntervalUs, currentIntervalUs + ramp);
  }
  nextStepAtUs = nowUs + currentIntervalUs;
}
