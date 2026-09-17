// Reçoit le flux ECG temps réel de Flask (SSE, /ecg-stream) et le transforme
// en messages 'veritometre/mesure' — le même format que le simulateur, donc
// la courbe (courbe.js) et les jauges (main.js) fonctionnent sans rien changer.
//
// Chaque évènement SSE ressemble à :
//   { signal: 512, bpm: 74, ecart: 3.2, leadsOff: false }
//   { signal: null, bpm: "--", ecart: 0, leadsOff: true }   // électrode décrochée

function demarrerECG(onMessage, options = {}) {
  const url = options.url || (location.origin + '/ecg-stream');
  const source = new EventSource(url);

  source.onmessage = (evt) => {
    let data;
    try {
      data = JSON.parse(evt.data);
    } catch (e) {
      return;
    }
    onMessage('veritometre/mesure', data);
  };

  source.onerror = () => {
    // EventSource se reconnecte tout seul ; on log juste pour le debug.
    console.warn('Flux ECG interrompu, reconnexion automatique…');
  };

  return {
    arreter() {
      source.close();
    }
  };
}
