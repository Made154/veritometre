// 'polling' = interroge Flask (/get-question) en boucle — solution actuelle avec n8n
// 'simu'    = données factices pour tester l'écran sans backend
// 'mqtt'    = broker MQTT (nécessite Mosquitto + un publisher côté Pi)
const MODE = 'polling';

const ETATS = ['attente', 'calibration', 'session', 'verdict', 'perdu'];
let etatActuel = null;
let controleurSimulateur = null;
let minuteurCalibration = null;
const DELAI_CALIBRATION_AUTO = 3000;

const ANNONCES_ETATS = {
  attente: 'Posez votre main sur les capteurs.',
  calibration: 'Étalonnage biométrique en cours. Ne bougez plus.',
  perdu: 'Contact perdu. Tentative de fuite détectée.'
};

function afficherEtat(etat) {
  if (!ETATS.includes(etat)) return;
  clearTimeout(minuteurCalibration);
  const changement = etat !== etatActuel;
  document.querySelectorAll('.ecran').forEach((el) => el.classList.remove('actif'));
  const cible = document.getElementById('ecran-' + etat);
  if (cible) cible.classList.add('actif');
  etatActuel = etat;

  if (etat === 'session') reinitialiserCourbe();
  if (changement && ANNONCES_ETATS[etat]) parler(ANNONCES_ETATS[etat]);

  if (changement && etat === 'calibration') {
    minuteurCalibration = setTimeout(() => {
      afficherEtat('session');
      annoncerQuestionAffichee();
    }, DELAI_CALIBRATION_AUTO);
  }
}

function afficherVerdict(resultat, score, reaction) {
  const texteReaction = document.getElementById('texte-reaction');
  const texte = document.getElementById('texte-verdict');
  const scoreEl = document.getElementById('score-verdict');

  const libelleVerdict = resultat === 'mensonge' ? 'MENSONGE' : 'VÉRITÉ';
  if (texteReaction) texteReaction.textContent = reaction || '';
  texte.textContent = libelleVerdict;
  texte.className = 'verdict ' + (resultat === 'mensonge' ? 'verdict-mensonge' : 'verdict-verite');
  scoreEl.textContent = (score || score === 0) ? score + '%' : '--';

  const annonce = reaction ? `${reaction} Verdict : ${libelleVerdict}.` : `${libelleVerdict}.`;
  parler(annonce);
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
      parler(payload.texte);
      break;
    case 'veritometre/verdict':
      afficherVerdict(payload.resultat, payload.score, payload.reaction);
      break;
  }
}

function annoncerVerdictAffiche() {
  const reactionEl = document.getElementById('texte-reaction');
  const verdictEl = document.getElementById('texte-verdict');
  const reaction = reactionEl ? reactionEl.textContent : '';
  const verdict = verdictEl ? verdictEl.textContent : '';
  const annonce = reaction && verdict ? `${reaction} Verdict : ${verdict}.` : (reaction || verdict);
  if (annonce) parler(annonce);
}

function annoncerQuestionAffichee() {
  const questionEl = document.getElementById('texte-question');
  if (questionEl && questionEl.textContent) parler(questionEl.textContent);
}

function annoncerEcran(etat) {
  if (etat === 'verdict') annoncerVerdictAffiche();
  if (etat === 'session') annoncerQuestionAffichee();
}

const TOUCHES_ETATS = {
  '1': 'attente', '2': 'calibration', '3': 'session', '4': 'verdict', '5': 'perdu'
};
document.addEventListener('keydown', (e) => {
  if (TOUCHES_ETATS[e.key]) {
    afficherEtat(TOUCHES_ETATS[e.key]);
    annoncerEcran(TOUCHES_ETATS[e.key]);
    return;
  }
  if (e.key === 'ArrowRight' && etatActuel === 'session' && controleurSimulateur) {
    controleurSimulateur.questionSuivante();
    return;
  }
  const i = ETATS.indexOf(etatActuel);
  let nouvelEtat = null;
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    nouvelEtat = ETATS[(i + 1 + ETATS.length) % ETATS.length];
  }
  if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    nouvelEtat = ETATS[(i - 1 + ETATS.length) % ETATS.length];
  }
  if (nouvelEtat) {
    afficherEtat(nouvelEtat);
    annoncerEcran(nouvelEtat);
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
