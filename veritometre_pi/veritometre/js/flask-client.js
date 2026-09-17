// Interroge périodiquement l'API Flask (/get-question) au lieu d'un broker MQTT.
// Le state renvoyé par Flask ressemble à :
//   { etat: 'session'|'avis'|'verdict'|'attente', question_suivante, avis, verdict, score }

function demarrerPolling(onMessage, options = {}) {
  const intervalleMs = options.intervalle || 1200;
  const url = options.url || (location.origin + '/get-question');
  let dernierEtatBrut = null;
  let actif = true;

  function traiterNouvelEtat(data) {
    if (data.etat === 'verdict' && data.verdict) {
      onMessage('veritometre/verdict', { resultat: data.verdict, score: data.score });
      onMessage('veritometre/etat', 'verdict');
    } else if (data.etat === 'avis' && data.avis) {
      onMessage('veritometre/avis', { avis: data.avis });
    } else if (data.question_suivante) {
      onMessage('veritometre/question', { texte: data.question_suivante });
    }
  }

  async function interroger() {
    if (!actif) return;
    try {
      const reponse = await fetch(url, { cache: 'no-store' });
      if (!reponse.ok) throw new Error('HTTP ' + reponse.status);
      const data = await reponse.json();
      const brut = JSON.stringify(data);

      if (brut !== dernierEtatBrut) {
        dernierEtatBrut = brut;
        traiterNouvelEtat(data);
      }
    } catch (err) {
      console.error('Erreur de polling Flask :', err);
    }
  }

  interroger();
  const minuteur = setInterval(interroger, intervalleMs);

  return {
    arreter() {
      actif = false;
      clearInterval(minuteur);
    }
  };
}
