const TOPICS = [
  'veritometre/etat',
  'veritometre/mesure',
  'veritometre/question',
  'veritometre/verdict'
];

function demarrerMQTT(onMessage, onStatut) {
  const url = 'ws://' + location.hostname + ':9001';
  const client = mqtt.connect(url);

  client.on('connect', () => {
    client.subscribe(TOPICS, (err) => {
      if (err) console.error('Erreur de souscription MQTT :', err);
    });
    if (onStatut) onStatut('connecte');
  });

  client.on('message', (topic, messageBrut) => {
    const texte = messageBrut.toString();
    let payload;
    try {
      payload = JSON.parse(texte);
    } catch (e) {
      payload = texte;
    }
    onMessage(topic, payload);
  });

  client.on('close', () => { if (onStatut) onStatut('deconnecte'); });
  client.on('error', (err) => console.error('Erreur MQTT :', err));

  return client;
}
