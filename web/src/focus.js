import * as THREE from 'three';
import { prefersReducedMotion } from './dom.js';

// Animações do foco: rotação dos globos (slerp) e câmera. Um tween novo na mesma chave cancela o anterior.
// Durante o tween da câmera o OrbitControls fica desligado; ele volta para o usuário quando o tween termina.

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const Y = new THREE.Vector3(0, 1, 0);
const X = new THREE.Vector3(1, 0, 0);
const Z = new THREE.Vector3(0, 0, 1);

export function createFocus({ camera, controls, canvas }) {
  const tweens = new Map();
  const offset = { x: 0, y: 0 }; // deslocamento do centro óptico, em px (ver setViewOffset)

  function tween(key, ms, step, done) {
    if (ms <= 0 || prefersReducedMotion()) {
      tweens.delete(key);
      step(1);
      done?.();
      return;
    }
    tweens.set(key, { t0: performance.now(), ms, step, done });
  }

  function applyOffset() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!w || !h) return;
    if (offset.x === 0 && offset.y === 0) camera.clearViewOffset();
    else camera.setViewOffset(w, h, offset.x, offset.y, w, h);
    camera.updateProjectionMatrix();
  }

  function setCamera(position, target, off) {
    camera.position.copy(position);
    controls.target.copy(target);
    camera.lookAt(target);
    offset.x = off.x;
    offset.y = off.y;
    applyOffset();
  }

  return {
    get cameraBusy() { return tweens.has('camera'); },

    /**
     * Gira o globo até o ponto (lat, lon) ficar virado para `cameraPosition`, com o norte para cima.
     * Qlon leva a longitude ao eixo +Z, Qlat inclina a latitude até +Z e Qdir aponta +Z para a câmera.
     */
    rotateGlobeTo(globe, lat, lon, cameraPosition, ms = 600) {
      const qLon = new THREE.Quaternion().setFromAxisAngle(Y, -THREE.MathUtils.degToRad(90 + lon));
      const qLat = new THREE.Quaternion().setFromAxisAngle(X, THREE.MathUtils.degToRad(lat));
      const dir = cameraPosition.clone().sub(globe.position).normalize();
      const end = new THREE.Quaternion().setFromUnitVectors(Z, dir).multiply(qLat).multiply(qLon);
      const start = globe.quaternion.clone();
      tween(`globe-${globe.name}`, ms, (k) => globe.quaternion.slerpQuaternions(start, end, k));
    },

    /** Leva a câmera até o enquadramento { position, target, offset } com animação. */
    flyTo(frame, ms = 700) {
      const p0 = camera.position.clone();
      const t0 = controls.target.clone();
      const o0 = { ...offset };
      const p = new THREE.Vector3();
      const t = new THREE.Vector3();
      controls.enabled = false;
      tween('camera', ms, (k) => {
        p.lerpVectors(p0, frame.position, k);
        t.lerpVectors(t0, frame.target, k);
        setCamera(p, t, {
          x: o0.x + (frame.offset.x - o0.x) * k,
          y: o0.y + (frame.offset.y - o0.y) * k,
        });
      }, () => {
        controls.enabled = true;
        controls.update();
      });
    },

    /** Sem animação (redimensionamento): mantém a direção em que o usuário deixou a câmera. */
    jumpTo(frame) {
      if (tweens.has('camera')) { this.flyTo(frame); return; }
      const dir = camera.position.clone().sub(controls.target);
      const dist = frame.position.distanceTo(frame.target);
      if (dir.lengthSq() === 0) dir.set(0, 0, 1);
      setCamera(dir.setLength(dist).add(frame.target), frame.target, frame.offset);
    },

    /** Chamar a cada frame, antes de renderizar. */
    update(now = performance.now()) {
      for (const [key, tw] of tweens) {
        const k = Math.min((now - tw.t0) / tw.ms, 1);
        tw.step(ease(k));
        if (k >= 1 && tweens.get(key) === tw) {
          tweens.delete(key);
          tw.done?.();
        }
      }
    },
  };
}
