#include <Adafruit_GFX.h>
#include <Adafruit_TFTLCD.h>
#include <TouchScreen.h>

// TFT Pin configuratie
#define LCD_CS A3
#define LCD_CD A2
#define LCD_WR A1
#define LCD_RD A0
#define LCD_RESET A4

// Touchscreen pinnen voor het standaard 2.8" Shield
#define YP A3  // must be an analog pin
#define XM A2  // must be an analog pin
#define YM 9   // can be a digital pin
#define XP 8   // can be a digital pin

// Touch druk-drempels
#define MINPRESSURE 10
#define MAXPRESSURE 1000

// Calibratiewaarden voor touchscreen (pas aan indien touch niet uitlijnt)
#define TS_MINX 150
#define TS_MINY 120
#define TS_MAXX 920
#define TS_MAXY 940

#define BLACK   0x0000
#define WHITE   0xFFFF
#define BLUE    0x001F
#define RED     0xF800
#define GREEN   0x07E0
#define MAGENTA 0xF81F
#define GREY    0x4208

Adafruit_TFTLCD tft(LCD_CS, LCD_CD, LCD_WR, LCD_RD, LCD_RESET);
TouchScreen ts = TouchScreen(XP, YP, XM, YM, 300);

// Structuur voor 4 knoppen
struct Button {
  int x, y, w, h;
  char label[12];
  uint16_t color;
};

Button buttons[4] = {
  { 10,  10, 145, 105, "Button",    RED },
  { 165, 10, 145, 105, "Button",  BLUE },
  { 10, 125, 145, 105, "Button", GREEN },
  { 165,125, 145, 105, "Button", MAGENTA }
};

unsigned long lastTouchTime = 0;

void drawButton(int i) {
  tft.fillRect(buttons[i].x, buttons[i].y, buttons[i].w, buttons[i].h, buttons[i].color);
  tft.drawRect(buttons[i].x, buttons[i].y, buttons[i].w, buttons[i].h, WHITE);
  
  tft.setTextColor(WHITE);
  tft.setTextSize(2);
  
  // Centreer tekst grofweg
  int textX = buttons[i].x + (buttons[i].w / 2) - (strlen(buttons[i].label) * 6);
  int textY = buttons[i].y + (buttons[i].h / 2) - 8;
  
  tft.setCursor(textX, textY);
  tft.print(buttons[i].label);
}

void drawAllButtons() {
  tft.fillScreen(BLACK);
  for (int i = 0; i < 4; i++) {
    drawButton(i);
  }
}

void setup() {
  Serial.begin(115200);
  tft.reset();
  uint16_t identifier = tft.readID();
  tft.begin(identifier);
  tft.setRotation(1); // Horizontale stand (320x240)
  
  drawAllButtons();
}

void loop() {
  // Lees touch-input
  digitalWrite(13, HIGH);
  TSPoint p = ts.getPoint();
  digitalWrite(13, LOW);

  pinMode(XM, OUTPUT);
  pinMode(YP, OUTPUT);

  if (p.z > MINPRESSURE && p.z < MAXPRESSURE) {
    if (millis() - lastTouchTime > 300) { // Debounce van 300ms
      // Mappen van touch coördinaten naar scherm pixels (320x240)
      int x = map(p.y, TS_MINY, TS_MAXY, tft.width(), 0);
      int y = map(p.x, TS_MINX, TS_MAXX, tft.height(), 0);

      for (int i = 0; i < 4; i++) {
        if (x >= buttons[i].x && x <= (buttons[i].x + buttons[i].w) &&
            y >= buttons[i].y && y <= (buttons[i].y + buttons[i].h)) {
          
          // Signaal sturen naar Python
          Serial.print("BTN_");
          Serial.println(i);
          
          // Visuele feedback op scherm
          tft.drawRect(buttons[i].x, buttons[i].y, buttons[i].w, buttons[i].h, BLACK);
          delay(100);
          tft.drawRect(buttons[i].x, buttons[i].y, buttons[i].w, buttons[i].h, WHITE);
          break;
        }
      }
      lastTouchTime = millis();
    }
  }

  // Verwerk inkomende commando's van Python (bijv. UPDATE:0:Discord:0x07E0)
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    if (input.startsWith("UPDATE:")) {
      int firstColon = input.indexOf(':');
      int secondColon = input.indexOf(':', firstColon + 1);
      int thirdColon = input.indexOf(':', secondColon + 1);

      int btnIndex = input.substring(firstColon + 1, secondColon).toInt();
      String newLabel = input.substring(secondColon + 1, thirdColon);
      uint16_t newColor = strtol(input.substring(thirdColon + 1).c_str(), NULL, 16);

      if (btnIndex >= 0 && btnIndex < 4) {
        newLabel.toCharArray(buttons[btnIndex].label, 12);
        buttons[btnIndex].color = newColor;
        drawButton(btnIndex);
      }
    }
  }
}
