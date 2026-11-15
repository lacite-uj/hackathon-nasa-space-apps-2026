import * as THREE from 'three';
import { MARKER_SIZE } from './globe.js';

// Hover e clique nos marcadores. Usa o raio do Raycaster contra uma esfera de toque em volta de cada
// marcador (maior que o marcador, para ser fácil de acertar) e contra os globos, que escondem os
// marcadores da face de trás.

const CLICK_TOLERANCE_PX = 5; // acima disso o gesto foi um arrasto do OrbitControls, não um clique

/**
 * @param {object} opts
 * @param {HTMLCanvasElement} opts.canvas
 * @param {THREE.Camera} opts.camera
 * @param {Record<string, THREE.Group>} opts.globes
 * @param {THREE.Object3D[]} opts.markers  marcadores clicáveis (userData.kind = 'analog' | 'target')
 * @param {HTMLElement} opts.tooltip
 * @param {(marker: THREE.Object3D | null) => void} opts.onHover
 * @param {(marker: THREE.Object3D | null) => void} opts.onClick  null = clique no vazio
 */
export function createInteraction({ canvas, camera, globes, markers, tooltip, onHover, onClick }) {
  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  const sphere = new THREE.Sphere();
  const hit = new THREE.Vector3();
  let hovered = null;
  let down = null;

  function pick(event) {
    const rect = canvas.getBoundingClientRect();
    ndc.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    const ray = raycaster.ray;

    let globeDistance = Infinity;
    for (const globe of Object.values(globes)) {
      globe.getWorldPosition(sphere.center);
      sphere.radius = globe.userData.radius;
      if (ray.intersectSphere(sphere, hit)) globeDistance = Math.min(globeDistance, hit.distanceTo(ray.origin));
    }

    const hitRadius = MARKER_SIZE * (event.pointerType === 'touch' ? 3.5 : 2.2);
    let best = null;
    let bestMiss = Infinity;
    for (const marker of markers) {
      marker.getWorldPosition(sphere.center);
      sphere.radius = hitRadius;
      if (!ray.intersectSphere(sphere, hit)) continue;
      if (hit.distanceTo(ray.origin) > globeDistance) continue; // atrás de um globo
      const miss = ray.distanceSqToPoint(sphere.center);        // o mais perto do raio vence
      if (miss < bestMiss) { bestMiss = miss; best = marker; }
    }
    return best;
  }

  function showTooltip(marker, event) {
    if (!marker) { tooltip.hidden = true; return; }
    tooltip.textContent = marker.userData.name ?? marker.name;
    tooltip.hidden = false;
    const x = Math.min(event.clientX + 14, window.innerWidth - tooltip.offsetWidth - 8);
    const y = Math.max(event.clientY - tooltip.offsetHeight - 10, 8);
    tooltip.style.transform = `translate(${Math.max(x, 8)}px, ${y}px)`;
  }

  function setHovered(marker, event) {
    if (marker !== hovered) {
      hovered = marker;
      canvas.style.cursor = marker ? 'pointer' : '';
      onHover(marker);
    }
    showTooltip(marker, event);
  }

  canvas.addEventListener('pointermove', (event) => {
    if (event.pointerType === 'touch' || event.buttons !== 0) return; // sem hover no toque nem durante o arrasto
    setHovered(pick(event), event);
  });
  canvas.addEventListener('pointerleave', (event) => setHovered(null, event));
  canvas.addEventListener('pointerdown', (event) => {
    down = { x: event.clientX, y: event.clientY, id: event.pointerId };
    tooltip.hidden = true;
  });
  canvas.addEventListener('pointerup', (event) => {
    if (!down || down.id !== event.pointerId) return;
    const moved = Math.hypot(event.clientX - down.x, event.clientY - down.y);
    down = null;
    if (moved > CLICK_TOLERANCE_PX || event.button !== 0) return;
    onClick(pick(event));
  });
  canvas.addEventListener('pointercancel', () => { down = null; });

  return { pick };
}
