const QUESTIONS = [
  { id: 1, texte: "Avez-vous déjà menti à Rick ?" },
  { id: 2, texte: "Avez-vous saboté le portal gun ?" },
  { id: 3, texte: "Summer sait-elle garder un secret ?" }
];

const DUREE_ATTENTE = 4000;
const DUREE_CALIBRATION = 3000;
const INTERVALLE_MESURE = 200;
const DUREE_RETOUR_CALME = 3500;

function demarrerSimulateur(onMessage) {
  let minuteur = null;
  let intervalleMesure = null;
  let actif = true;
  let passerQuestion = null;
  let indexQuestion = 0;

  function publier(topic, payload) {
    if (actif) onMessage(topic, payload);
  }

  function genererMesure(t, base) {
    const oscillation = Math.sin(t) * 15;
    const bruit = (Math.random() - 0.5) * 8;
    const pic = Math.random() < 0.04 ? 60 + Math.random() * 120 : 0;
    const gsr = base + oscillation + bruit + pic;
    const ecart = ((gsr - base) / base) * 100;
    const bpm = 72 + Math.sin(t * 0.5) * 6 + (pic > 0 ? 10 : 0) + (Math.random() - 0.5) * 3;
    return {
      gsr: Math.round(gsr),
      base: Math.round(base),
      ecart: Number(ecart.toFixed(1)),
      bpm: Math.round(bpm)
    };
  }

  function cycleAttente() {
    publier('veritometre/etat', 'attente');
    minuteur = setTimeout(demarrerExamen, DUREE_ATTENTE);
  }

  function demarrerExamen() {
    indexQuestion = 0;
    cycleCalibration();
  }

  function cycleCalibration() {
    publier('veritometre/etat', 'calibration');
    minuteur = setTimeout(cycleQuestion, DUREE_CALIBRATION);
  }

  function cycleQuestion() {
    publier('veritometre/etat', 'session');
    publier('veritometre/question', QUESTIONS[indexQuestion]);

    const base = 1550 + Math.random() * 200;
    let t = 0;
    let ecartMaxQuestion = 0;

    intervalleMesure = setInterval(() => {
      t += 0.15;
      const mesure = genererMesure(t, base);
      ecartMaxQuestion = Math.max(ecartMaxQuestion, Math.abs(mesure.ecart));
      publier('veritometre/mesure', mesure);
    }, INTERVALLE_MESURE);

    passerQuestion = () => {
      clearInterval(intervalleMesure);
      passerQuestion = null;
      cycleVerdict(ecartMaxQuestion);
    };
  }

  function cycleVerdict(ecartQuestion) {
    const score = Math.min(100, Math.round(ecartQuestion * 1.4));
    const resultat = score >= 50 ? 'mensonge' : 'verite';

    publier('veritometre/etat', 'verdict');
    publier('veritometre/verdict', { resultat, score });

    indexQuestion++;
    const suite = indexQuestion < QUESTIONS.length ? cycleCalibration : demarrerExamen;
    minuteur = setTimeout(suite, DUREE_RETOUR_CALME);
  }

  cycleAttente();

  return {
    arreter() {
      actif = false;
      clearTimeout(minuteur);
      clearInterval(intervalleMesure);
    },
    questionSuivante() {
      if (passerQuestion) passerQuestion();
    }
  };
}
