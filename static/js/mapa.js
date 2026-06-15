/* Mapa do técnico - MapLibre + sidebar + modal */

const TILES = {
  osm: {
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    attribution: '© OpenStreetMap'
  },
  light: {
    tiles: [
      'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
      'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
      'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'
    ],
    attribution: '© OpenStreetMap © CARTO'
  }
};

let activeTile = 'osm';
let projeto = null;
let postesById = {};
let selectedPosteId = null;

function rasterStyle(key) {
  const b = TILES[key] || TILES.osm;
  return {
    version: 8,
    sources: { base: { type: 'raster', tiles: b.tiles, tileSize: 256, attribution: b.attribution } },
    layers: [{ id: 'base', type: 'raster', source: 'base' }]
  };
}

const map = new maplibregl.Map({
  container: 'map',
  style: rasterStyle(activeTile),
  center: [-47.45, -23.5],
  zoom: 9
});
map.addControl(new maplibregl.NavigationControl(), 'bottom-right');

// Captura da localização do usuário
const geolocate = new maplibregl.GeolocateControl({
  positionOptions: { enableHighAccuracy: true },
  trackUserLocation: true,
  showUserLocation: true,
  showAccuracyCircle: true
});
map.addControl(geolocate, 'bottom-right');

// Busca de endereço (geocoder via Nominatim / OpenStreetMap)
if (window.MaplibreGeocoder) {
  const geocoderApi = {
    forwardGeocode: async (config) => {
      const features = [];
      try {
        const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(config.query)}` +
                    `&format=geojson&polygon_geojson=0&addressdetails=1&limit=5&countrycodes=br`;
        const res = await fetch(url, { headers: { 'Accept-Language': 'pt-BR' } });
        const geojson = await res.json();
        (geojson.features || []).forEach(f => {
          const center = [
            f.bbox ? (f.bbox[0] + f.bbox[2]) / 2 : f.geometry.coordinates[0],
            f.bbox ? (f.bbox[1] + f.bbox[3]) / 2 : f.geometry.coordinates[1]
          ];
          features.push({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: center },
            place_name: f.properties.display_name,
            properties: f.properties,
            text: f.properties.display_name,
            place_type: ['place'],
            center
          });
        });
      } catch (e) { console.error('Geocoder erro:', e); }
      return { features };
    }
  };
  const geocoder = new MaplibreGeocoder(geocoderApi, {
    maplibregl: maplibregl,
    placeholder: 'Buscar endereço...',
    marker: { color: '#ef4444' },
    showResultsWhileTyping: true,
    minLength: 3,
    limit: 5
  });
  map.addControl(geocoder, 'top-left');
}

function postesGeoJSON() {
  return {
    type: 'FeatureCollection',
    features: Object.values(postesById).map(p => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.longitude, p.latitude] },
      properties: { id: p.id, preenchido: p.preenchido }
    }))
  };
}

function addPostesLayer() {
  if (map.getSource('postes')) {
    map.getSource('postes').setData(postesGeoJSON());
    return;
  }
  map.addSource('postes', { type: 'geojson', data: postesGeoJSON() });
  map.addLayer({
    id: 'postes-circle',
    type: 'circle',
    source: 'postes',
    paint: {
      'circle-radius': 8,
      'circle-color': '#22c55e',
      'circle-stroke-width': 2,
      'circle-stroke-color': ['case', ['get', 'preenchido'], '#065f46', '#ffffff'],
      'circle-opacity': 0.95
    }
  });
  map.on('click', 'postes-circle', e => openModal(e.features[0].properties.id));
  map.on('mouseenter', 'postes-circle', () => map.getCanvas().style.cursor = 'pointer');
  map.on('mouseleave', 'postes-circle', () => map.getCanvas().style.cursor = '');
}

async function loadProjeto() {
  if (!PROJECT_ID) return;
  const res = await fetch(`/api/projeto/${PROJECT_ID}`);
  projeto = await res.json();
  postesById = {};
  projeto.postes.forEach(p => postesById[p.id] = p);
  addPostesLayer();
  fitToPostes();
  renderStatus();
}

function fitToPostes() {
  const feats = Object.values(postesById);
  if (!feats.length) return;
  const b = new maplibregl.LngLatBounds();
  feats.forEach(p => b.extend([p.longitude, p.latitude]));
  map.fitBounds(b, { padding: 80, maxZoom: 17 });
}

/* ---------- status do projeto ---------- */
function renderStatus() {
  const el = document.getElementById('proj-status');
  const btn = document.getElementById('btn-toggle-status');
  if (!el || !projeto) return;
  const encerrado = projeto.status === 'encerrado';
  el.textContent = encerrado ? 'Encerrado' : 'Aberto';
  el.className = 'px-2 py-1 rounded-full text-xs font-medium ' +
    (encerrado ? 'bg-slate-200 text-slate-600' : 'bg-emerald-100 text-emerald-700');
  btn.textContent = encerrado ? 'Reabrir / Alterar' : 'Encerrar projeto';
  btn.className = 'ml-2 px-3 py-1.5 rounded-lg text-sm font-medium text-white ' +
    (encerrado ? 'bg-slate-600 hover:bg-slate-700' : 'bg-brand-600 hover:bg-brand-700');
}

document.getElementById('btn-toggle-status')?.addEventListener('click', async () => {
  const novo = projeto.status === 'encerrado' ? 'aberto' : 'encerrado';
  const res = await fetch(`/api/projeto/${PROJECT_ID}/status`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: novo })
  });
  const data = await res.json();
  projeto.status = data.status;
  renderStatus();
});

/* ---------- tiles ---------- */
document.querySelectorAll('.tile-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    activeTile = btn.dataset.tile;
    map.setStyle(rasterStyle(activeTile));
    map.once('styledata', () => addPostesLayer());
    syncTileButtons();
  });
});
function syncTileButtons() {
  document.querySelectorAll('.tile-btn').forEach(b => {
    const on = b.dataset.tile === activeTile;
    b.className = 'tile-btn px-3 py-1.5 rounded-lg text-sm font-medium ' +
      (on ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100');
  });
}

/* ---------- modal ---------- */
const modal = document.getElementById('modal');
function openModal(id) {
  selectedPosteId = id;
  document.getElementById('modal-title').textContent = 'Poste #' + id;
  modal.classList.remove('hidden');
  modal.classList.add('flex');
}
function closeModal() {
  modal.classList.add('hidden');
  modal.classList.remove('flex');
}
document.getElementById('modal-cancel').addEventListener('click', closeModal);
document.getElementById('modal-edit').addEventListener('click', () => { closeModal(); openSidebar(selectedPosteId); });
document.getElementById('modal-route').addEventListener('click', () => {
  const p = postesById[selectedPosteId];
  if (p) window.open(`https://www.google.com/maps/dir/?api=1&destination=${p.latitude},${p.longitude}`, '_blank');
  closeModal();
});

/* ---------- sidebar ---------- */
const sidebar = document.getElementById('sidebar');
function openSidebar(id) {
  selectedPosteId = id;
  const p = postesById[id];
  document.getElementById('sb-title').textContent = 'Poste #' + id;
  document.getElementById('sb-obs').value = p.observacoes || '';
  renderFotos(p);
  sidebar.classList.remove('-translate-x-full');
}
function closeSidebar() { sidebar.classList.add('-translate-x-full'); }
document.getElementById('sb-close').addEventListener('click', closeSidebar);

function renderFotos(p) {
  const wrap = document.getElementById('sb-fotos');
  wrap.innerHTML = '';
  p.photos.forEach(ph => {
    const div = document.createElement('div');
    div.className = 'relative aspect-square rounded-lg overflow-hidden border border-slate-200 group';
    div.innerHTML = `<img src="${ph.url}" class="w-full h-full object-cover">
      <button data-photo="${ph.id}" class="del-foto absolute top-1 right-1 w-6 h-6 rounded-full bg-black/60 text-white text-xs opacity-0 group-hover:opacity-100">×</button>`;
    wrap.appendChild(div);
  });
  document.getElementById('sb-foto-count').textContent = `${p.photos.length}/3`;
  const addBtn = document.getElementById('sb-foto-add');
  addBtn.style.display = p.photos.length >= 3 ? 'none' : 'flex';
  wrap.querySelectorAll('.del-foto').forEach(b => {
    b.addEventListener('click', () => deleteFoto(b.dataset.photo));
  });
}

document.getElementById('sb-foto-input').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('foto', file);
  const res = await fetch(`/api/poste/${selectedPosteId}/foto`, { method: 'POST', body: fd });
  const data = await res.json();
  e.target.value = '';
  if (!res.ok) { alert(data.error || 'Erro ao enviar foto'); return; }
  postesById[selectedPosteId] = data;
  renderFotos(data);
});

async function deleteFoto(photoId) {
  const res = await fetch(`/api/poste/${selectedPosteId}/foto/${photoId}`, { method: 'DELETE' });
  const data = await res.json();
  postesById[selectedPosteId] = data;
  renderFotos(data);
}

document.getElementById('sb-save').addEventListener('click', async () => {
  const obs = document.getElementById('sb-obs').value;
  const res = await fetch(`/api/poste/${selectedPosteId}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ observacoes: obs })
  });
  const data = await res.json();
  postesById[selectedPosteId] = data;
  if (map.getSource('postes')) map.getSource('postes').setData(postesGeoJSON());
  closeSidebar();
});

/* ---------- init ---------- */
map.on('load', () => { syncTileButtons(); loadProjeto(); });
