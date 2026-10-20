import { storageRead } from './data.js';

const osmCredit = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors';
const streets = {
  id: 'streets',
  url: import.meta.env?.VITE_MAP_TILES || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  tileSize: 256, maxZoom: 19, saturation: -0.55, darkBrightness: 0.55, alpha: false,
  attribution: osmCredit,
};
const satellite = {
  id: 'satellite',
  url: 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg',
  tileSize: 256, maxZoom: 14, saturation: 0, darkBrightness: 0.9, alpha: false,
  attribution: '<a href="https://cloudless.eox.at" target="_blank" rel="noreferrer">EOxCloudless</a> by EOX IT Services GmbH · Contains modified Copernicus Sentinel data 2016 · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a>',
};
const labels = {
  id: 'satellite-labels',
  url: 'https://tiles.maps.eox.at/wmts/1.0.0/overlay_bright_3857/default/g/{z}/{y}/{x}.png',
  tileSize: 256, maxZoom: 14, saturation: 0, darkBrightness: 1, alpha: true,
  attribution: `${osmCredit} · Overlay rendering © <a href="https://maps.eox.at" target="_blank" rel="noreferrer">EOX</a> and MapServer`,
};
const topographic = {
  id: 'topographic',
  url: 'https://tile.opentopomap.org/{z}/{x}/{y}.png',
  tileSize: 256, maxZoom: 17, saturation: 0, darkBrightness: 0.65, alpha: false,
  attribution: `${osmCredit} · Elevation: SRTM/Sonny · Map: © <a href="https://opentopomap.org/about" target="_blank" rel="noreferrer">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" rel="noreferrer">CC BY-SA 3.0</a>)`,
};

export const basemaps = [
  { id: 'streets', label: 'Streets', layers: [streets] },
  { id: 'satellite', label: 'Satellite · 2016', layers: [satellite] },
  { id: 'hybrid', label: 'Satellite + labels · 2016', layers: [satellite, labels] },
  { id: 'topographic', label: 'Topographic', layers: [topographic] },
];

export function getBasemap(id) {
  return basemaps.find(map => map.id === id) || basemaps[0];
}

export function savedImagery() {
  return getBasemap(storageRead('scripture-map-imagery', 'streets')).id;
}
