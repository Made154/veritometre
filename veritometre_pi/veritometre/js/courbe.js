const HISTORIQUE_MAX = 100;

let ctxCourbe = null;
let canvasCourbe = null;
let historiqueBpm = [];

function initCourbe(idCanvas) {
  canvasCourbe = document.getElementById(idCanvas);
  ctxCourbe = canvasCourbe.getContext('2d');
}

function reinitialiserCourbe() {
  historiqueBpm = [];
  dessinerCourbe();
}

function ajouterPointCourbe(bpm) {
  historiqueBpm.push(bpm);
  if (historiqueBpm.length > HISTORIQUE_MAX) {
    historiqueBpm.shift();
  }
  dessinerCourbe();
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
  historiqueBpm.forEach((bpm, i) => {
    const x = (decalage + i) * echelleX;
    const y = projeterY(bpm);
    if (i === 0) ctxCourbe.moveTo(x, y);
    else ctxCourbe.lineTo(x, y);
  });
  ctxCourbe.stroke();
}
