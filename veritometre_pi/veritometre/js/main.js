// 'polling' = interroge Flask (/get-question) en boucle — solution actuelle avec n8n
// 'simu'    = données factices pour tester l'écran sans backend
// 'mqtt'    = broker MQTT (nécessite Mosquitto + un publisher côté Pi)
const MODE = 'polling';

const ETATS = ['attente', 'calibration', 'session', 'avis', 'verdict', 'perdu', 'faux'];
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

function afficherAvis(avis) {
  const texte = document.getElementById('texte-avis');
  texte.textContent = avis === 'faux' ? 'FAUX' : 'VRAI';
  texte.className = 'verdict ' + (avis === 'faux' ? 'verdict-mensonge' : 'verdict-verite');
  afficherEtat('avis');
}

function afficherVerdict(resultat, score) {
  const texte = document.getElementById('texte-verdict');
  const scoreEl = document.getElementById('score-verdict');
  const scoreLabel = document.querySelector('#ecran-verdict .score-etiquette');
  texte.textContent = resultat === 'mensonge' ? 'MENSONGE' : 'VÉRITÉ';
  texte.className = 'verdict ' + (resultat === 'mensonge' ? 'verdict-mensonge' : 'verdict-verite');
  // Pas de score par tour (jugement d'une réponse) -> on masque la ligne SCORE.
  const aScore = score !== null && score !== undefined && score !== '';
  scoreEl.textContent = aScore ? score + '%' : '';
  scoreEl.hidden = !aScore;
  if (scoreLabel) scoreLabel.hidden = !aScore;
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

// Les réponses "oui"/"non" ne viennent plus de boutons tactiles mais du micro :
// c'est app.py (Vosk) qui écoute et relaie la réponse à n8n. La page n'a donc
// plus rien à envoyer — elle se contente d'afficher la question et l'ECG.

function gererMessage(topic, payload) {
  switch (topic) {
    case 'veritometre/etat':
      afficherEtat(payload);
      break;
    case 'veritometre/mesure':
      // 'signal' = échantillon ECG brut (Arduino) ; le simulateur, lui, n'envoie
      // que 'bpm' — on retombe dessus pour rester rétro-compatible.
      if (typeof payload.signal === 'number') ajouterPointCourbe(payload.signal);
      else if (typeof payload.bpm === 'number') ajouterPointCourbe(payload.bpm);
      if (payload.ecart != null) majJauge(payload.ecart);
      if (payload.bpm != null) majBpm(payload.bpm);
      break;
    case 'veritometre/question':
      document.getElementById('texte-question').textContent = payload.texte;
      if (etatActuel !== 'session') afficherEtat('session');
      break;
    case 'veritometre/avis':
      afficherAvis(payload.avis);
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
  // Entrée ou Espace sur l'écran d'attente -> démarre l'interrogatoire (sans souris)
  if ((e.key === 'Enter' || e.key === ' ') && etatActuel === 'attente') {
    e.preventDefault();
    demarrerInterrogatoire();
    return;
  }
  // Réponse au clavier (secours si le micro ne marche pas) : O = oui, N = non
  if ((e.key === 'o' || e.key === 'O') && etatActuel === 'session') {
    repondreClavier('oui');
    return;
  }
  if ((e.key === 'n' || e.key === 'N') && etatActuel === 'session') {
    repondreClavier('non');
    return;
  }
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

// Secours clavier : envoie une réponse oui/non à Flask (même chemin que le micro).
function repondreClavier(reponse) {
  fetch('/reponse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer: reponse })
  }).catch((err) => console.error('Erreur réponse clavier :', err));
}

let demarrageEnCours = false;
function demarrerInterrogatoire() {
  if (demarrageEnCours || etatActuel !== 'attente') return;
  demarrageEnCours = true;
  fetch('/demarrer', { method: 'POST' })
    .catch((err) => console.error('Erreur démarrage :', err))
    .finally(() => { demarrageEnCours = false; });
}

window.addEventListener('DOMContentLoaded', () => {
  initCourbe('canvas-courbe');
  afficherEtat('attente');

  // Appui sur l'écran d'attente ("posez votre main") -> lance l'interrogatoire.
  // Tactile ou clic ; n8n renvoie la 1ʳᵉ question, le polling l'affiche ensuite.
  const ecranAttente = document.getElementById('ecran-attente');
  if (ecranAttente) {
    ecranAttente.addEventListener('click', demarrerInterrogatoire);
    ecranAttente.addEventListener('touchstart', demarrerInterrogatoire, { passive: true });
  }

  if (MODE === 'simu') {
    controleurSimulateur = demarrerSimulateur(gererMessage);
  } else if (MODE === 'mqtt') {
    demarrerMQTT(gererMessage);
  } else if (MODE === 'polling') {
    demarrerPolling(gererMessage);   // questions / verdicts (n8n via Flask)
    demarrerECG(gererMessage);        // courbe ECG temps réel (Arduino via SSE)
  }
});
