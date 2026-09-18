/*
  Véritomètre — capteur ECG AD8232  (à téléverser sur l'Arduino Mega)
  ------------------------------------------------------------------
  Câblage (module AD8232 -> Arduino Mega) :
      AD8232 GND    -> GND
      AD8232 3.3V   -> 3.3V     (PAS 5V : le module est en 3.3V)
      AD8232 OUTPUT -> A0       (signal ECG analogique)
      AD8232 LO+    -> D11      (détection électrode décrochée)
      AD8232 LO-    -> D10      (détection électrode décrochée)
      AD8232 SDN    -> non connecté

  Électrodes (3 contacts) — répartis des DEUX côtés du corps :
      RA -> main/bras DROIT
      LA -> main/bras GAUCHE
      RL -> jambe/3e doigt (référence/masse)

  Sortie série (une ligne par échantillon) :
      "512"  -> valeur ECG brute 0..1023
      "!"    -> au moins une électrode décrochée (leads-off)

  Débit série : 115200 bauds.  Cadence : ~125 Hz.
  (app.py auto-détecte le débit, mais garde le moniteur série sur 115200.)
*/

const int BROCHE_ECG = A0;        // OUTPUT du module
const int BROCHE_LO_PLUS  = 11;   // LO+
const int BROCHE_LO_MOINS = 10;   // LO-

const unsigned long PERIODE_US = 8000UL;  // 125 Hz
unsigned long prochainEnvoi = 0;

void setup() {
  Serial.begin(115200);
  pinMode(BROCHE_LO_PLUS, INPUT);
  pinMode(BROCHE_LO_MOINS, INPUT);
  prochainEnvoi = micros();
}

// Détection "leads-off" désactivée : sur ce montage les broches LO+/LO-
// clignotent (~60% de faux "!"), ce qui hache le tracé. On envoie donc TOUJOURS
// la valeur brute A0 -> courbe continue (bruitée mais vivante, très "véritomètre").
// Pour réactiver la détection, remets le bloc if(LO...) ci-dessous.
void loop() {
  unsigned long maintenant = micros();

  // Cadence fixe : une mesure toutes les PERIODE_US.
  if ((long)(maintenant - prochainEnvoi) < 0) return;
  prochainEnvoi += PERIODE_US;

  Serial.println(analogRead(BROCHE_ECG));  // toujours la valeur brute

  // --- Ancienne détection leads-off (désactivée) ---
  // if (digitalRead(BROCHE_LO_PLUS) == HIGH || digitalRead(BROCHE_LO_MOINS) == HIGH)
  //   Serial.println('!');
  // else
  //   Serial.println(analogRead(BROCHE_ECG));
}
