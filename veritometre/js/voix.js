let utterancesEnAttente = [];

function parler(texte) {
  if (!('speechSynthesis' in window)) return;

  const voix = new SpeechSynthesisUtterance(texte);
  voix.lang = 'fr-FR';
  voix.rate = 0.9;   
  voix.pitch = 0.7;
  voix.onend = voix.onerror = () => {
    utterancesEnAttente = utterancesEnAttente.filter((u) => u !== voix);
  };

  utterancesEnAttente.push(voix);
  speechSynthesis.speak(voix);
}
