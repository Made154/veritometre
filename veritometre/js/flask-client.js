// Interroge périodiquement l'API Flask (/get-question) au lieu d'un broker MQTT.
// Appelle onMessage('veritometre/question', { texte }) quand la question change.

function demarrerPolling(onMessage, options = {}) {
  const intervalleMs = options.intervalle || 1500;
  const url = options.url || (location.origin + '/get-question');
  let derniereQuestion = null;
  let actif = true;

  async function interroger() {
    if (!actif) return;
    try {
      const reponse = await fetch(url, { cache: 'no-store' });
      if (!reponse.ok) throw new Error('HTTP ' + reponse.status);
      const data = await reponse.json();

      if (data.question && data.question !== derniereQuestion) {
        derniereQuestion = data.question;
        onMessage('veritometre/question', { texte: data.question });
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
