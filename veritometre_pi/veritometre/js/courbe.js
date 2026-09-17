// Nombre de points affichés. À 125 Hz (cadence de l'Arduino ECG), 250 points
// = ~2 s de tracé visible qui défilent, façon moniteur cardiaque.
// Le simulateur (qui envoie des BPM lents) fonctionne tout aussi bien.
const HISTORIQUE_MAX = 250;

let ctxCourbe = null;
let canvasCourbe = null;
let historiqueBpm = [];
let redessinDemande = false;

function initCourbe(idCanvas) {
  canvasCourbe = document.getElementById(idCanvas);
  ctxCourbe = canvasCourbe.getContext('2d');
}

function reinitialiserCourbe() {
  historiqueBpm = [];
  planifierRedessin();
}

function ajouterPointCourbe(valeur) {
  historiqueBpm.push(valeur);
  if (historiqueBpm.length > HISTORIQUE_MAX) {
    historiqueBpm.shift();
  }
  planifierRedessin();
}

// Les échantillons ECG arrivent vite (~125/s) ; on ne redessine qu'une fois par
// frame d'affichage (~60/s) pour rester fluide sans saturer le CPU du Pi.
function planifierRedessin() {
  if (redessinDemande) return;
  redessinDemande = true;
  requestAnimationFrame(() => {
    redessinDemande = false;
    dessinerCourbe();
  });
}

function dessinerCourbe() {
  if (!ctxCourbe) return;
  const largeur = canvasCourbe.width;
  const hauteur = canvasCourbe.height;
  ctxCourbe.clearRect(0, 0, largeur, hauteur);

  if (historiqueBpm.length < 2) return;

  let min = Math.min(...historiqueBpm) - 5;
  let max = Math.max(...historiqueBpm) + 5;
  if (max - min < 15) { min -= 7; max += 7; }

  const echelleX = largeur / (HISTORIQUE_MAX - 1);
  const projeterY = (v) => hauteur - ((v - min) / (max - min)) * hauteur;

  const decalage = HISTORIQUE_MAX - historiqueBpm.length;
  ctxCourbe.strokeStyle = '#39FF14';
  ctxCourbe.lineWidth = 2;
  ctxCourbe.beginPath();
  historiqueBpm.forEach((valeur, i) => {
    const x = (decalage + i) * echelleX;
    const y = projeterY(valeur);
    if (i === 0) ctxCourbe.moveTo(x, y);
    else ctxCourbe.lineTo(x, y);
  });
  ctxCourbe.stroke();
}
