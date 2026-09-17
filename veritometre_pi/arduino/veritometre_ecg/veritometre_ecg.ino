/*
  Véritomètre — capteur ECG AD8232  (kit "electrodos ECG")
  ---------------------------------------------------------
  Câblage (module AD8232 -> Arduino Uno/Nano) :
      AD8232 GND    -> GND
      AD8232 3.3V   -> 3.3V     (PAS 5V : le module est en 3.3V)
      AD8232 OUTPUT -> A0       (signal ECG analogique)
      AD8232 LO+    -> D11      (détection électrode décrochée)
      AD8232 LO-    -> D10      (détection électrode décrochée)
      AD8232 SDN    -> non connecté (ou 3.3V pour rester allumé)

  Électrodes (3 pinces) :
      RA (Right Arm)  -> sous la clavicule droite
      LA (Left Arm)   -> sous la clavicule gauche
      RL (Right Leg)  -> côté droit, bas des côtes  (masse)

  Format envoyé sur le port série (une ligne par échantillon) :
      "512"   -> valeur ECG brute, 0..1023 (10 bits)
      "!"     -> au moins une électrode est décrochée (leads-off)

  Débit série : 115200 bauds.
  Fréquence d'échantillonnage : ~125 Hz (voir PERIODE_US).
*/

const int BROCHE_ECG = A0;   // sortie analogique du module
const int BROCHE_LO_PLUS  = 11;  // LO+
const int BROCHE_LO_MOINS = 10;  // LO-

// 125 Hz -> une mesure toutes les 8000 microsecondes.
const unsigned long PERIODE_US = 8000UL;
unsigned long prochainEnvoi = 0;

void setup() {
  Serial.begin(115200);
  pinMode(BROCHE_LO_PLUS, INPUT);
  pinMode(BROCHE_LO_MOINS, INPUT);
  prochainEnvoi = micros();
}

void loop() {
  unsigned long maintenant = micros();

  // Cadence fixe : on n'envoie que toutes les PERIODE_US, quoi qu'il arrive.
  // (la soustraction non signée gère proprement le débordement de micros())
  if ((long)(maintenant - prochainEnvoi) < 0) return;
  prochainEnvoi += PERIODE_US;

  // Électrode décrochée ? -> on signale une "perte de contact".
  if (digitalRead(BROCHE_LO_PLUS) == HIGH || digitalRead(BROCHE_LO_MOINS) == HIGH) {
    Serial.println('!');
  } else {
    Serial.println(analogRead(BROCHE_ECG));
  }
}
