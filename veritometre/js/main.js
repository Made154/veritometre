// 'polling' = interroge Flask (/get-question) en boucle — solution actuelle avec n8n
// 'simu'    = données factices pour tester l'écran sans backend
// 'mqtt'    = broker MQTT (nécessite Mosquitto + un publisher côté Pi)
const MODE = 'polling';

const ETATS = ['attente', 'calibration', 'session', 'verdict', 'perdu'];
let etatActuel = null;
let controleurSimulateur = null;

function afficherEtat(etat) {
  if (!ETATS.includes(etat)) return;
  document.querySelectorAll('.ecran').forEach((el) => el.classList.remove('actif'));
  const cible = document.getElementById('ecran-' + etat);
  if (cible) cible.classList.add('actif');
  etatActuel = etat;

  if (etat === 'session') reinitialiserCourbe();
}

function afficherVerdict(resultat, score) {
  const texte = document.getElementById('texte-verdict');
  const scoreEl = document.getElementById('score-verdict');
  texte.textContent = resultat === 'mensonge' ? 'MENSONGE' : 'VÉRITÉ';
  texte.className = 'verdict ' + (resultat === 'mensonge' ? 'verdict-mensonge' : 'verdict-verite');
  scoreEl.textContent = score + '%';
}

function majJauge(ecart) {
  const jauge = document.getElementById('jauge-ecart');
  const valeur = document.getElementById('valeur-ecart');
  if (!jauge || !valeur) return;
  const pourcentage = Math.max(0, Math.min(100, Math.abs(ecart)));
  jauge.style.width = pourcentage + '%';
  valeur.textContent = ecart.toFixed(1) + '%';
}

function majBpm(bpm) {
  const el = document.getElementById('valeur-bpm');
  if (el) el.textContent = bpm;
}

function gererMessage(topic, payload) {
  switch (topic) {
    case 'veritometre/etat':
      afficherEtat(payload);
      break;
    case 'veritometre/mesure':
      ajouterPointCourbe(payload.bpm);
      majJauge(payload.ecart);
      majBpm(payload.bpm);
      break;
    case 'veritometre/question':
      document.getElementById('texte-question').textContent = payload.texte;
      if (etatActuel !== 'session') afficherEtat('session');
      break;
    case 'veritometre/verdict':
      afficherVerdict(payload.resultat, payload.score);
      break;
  }
}

const TOUCHES_ETATS = {
  '1': 'attente', '2': 'calibration', '3': 'session', '4': 'verdict', '5': 'perdu'
};
document.addEventListener('keydown', (e) => {
  if (TOUCHES_ETATS[e.key]) {
    afficherEtat(TOUCHES_ETATS[e.key]);
    return;
  }
  if (e.key === 'ArrowRight' && etatActuel === 'session' && controleurSimulateur) {
    controleurSimulateur.questionSuivante();
    return;
  }
  const i = ETATS.indexOf(etatActuel);
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    afficherEtat(ETATS[(i + 1 + ETATS.length) % ETATS.length]);
  }
  if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    afficherEtat(ETATS[(i - 1 + ETATS.length) % ETATS.length]);
  }
});

window.addEventListener('DOMContentLoaded', () => {
  initCourbe('canvas-courbe');
  afficherEtat('attente');

  if (MODE === 'simu') {
    controleurSimulateur = demarrerSimulateur(gererMessage);
  } else if (MODE === 'mqtt') {
    demarrerMQTT(gererMessage);
  } else if (MODE === 'polling') {
    demarrerPolling(gererMessage);
  }
});
