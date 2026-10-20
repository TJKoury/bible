<script>
  import { onMount } from 'svelte';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import mapWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
  import Icon from './Icon.svelte';
  let { points = [], mode = '2d', theme = 'light', selected = '', onSelect = () => {} } = $props();
  let container;
  let map;
  let library;
  let markers = [];
  let ready = $state(false);
  let failure = $state('');
  let tileFailure = $state(false);
  let retry = $state(0);
  let boundsKey = '';
  let appliedMode = '';
  onMount(() => {
    let disposed = false;
    let resize;
    async function start() {
      try {
        library = await import('maplibre-gl');
        if (disposed) return;
        library.setWorkerUrl(mapWorkerUrl);
        map = new library.Map({
          container,
          center: [35.5, 32], zoom: 6, maxZoom: 16, maxPitch: 80,
          attributionControl: { compact: false },
          style: {
            version: 8,
            sources: {
              land: {
                type: 'raster', tileSize: 256, maxzoom: 19,
                tiles: [import.meta.env.VITE_MAP_TILES || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
              },
              elevation: { type: 'raster-dem', url: 'https://tiles.mapterhorn.com/tilejson.json' },
            },
            layers: [{ id: 'land', type: 'raster', source: 'land', paint: { 'raster-saturation': -0.55 } }],
          },
        });
        map.addControl(new library.NavigationControl({ visualizePitch: true }), 'top-right');
        map.on('load', () => { if (!disposed) ready = true; });
        map.on('error', () => { if (!disposed) tileFailure = true; });
        resize = new ResizeObserver(() => map?.resize());
        resize.observe(container);
      } catch (e) {
        failure = 'The interactive map could not start. Coordinates and place sources are still available below.';
      }
    }
    start();
    return () => { disposed = true; resize?.disconnect(); markers.forEach(m => m.remove()); map?.remove(); };
  });
  $effect(() => {
    const loaded = ready; const current = points; const chosen = selected; const dimension = mode;
    if (!loaded || !map) return;
    markers.forEach(marker => marker.remove()); markers = [];
    for (const point of current) {
      const element = document.createElement('button');
      element.className = `atlas-pin ${point.disputed ? 'candidate' : ''} ${chosen === point.placeId ? 'chosen' : ''}`;
      element.setAttribute('aria-label', point.label);
      element.title = point.label;
      element.textContent = point.disputed ? '◇' : '●';
      element.onclick = () => onSelect(point.placeId);
      markers.push(new library.Marker({ element }).setLngLat([point.lon, point.lat]).addTo(map));
    }
    const key = current.map(p => `${p.key}:${p.lon}:${p.lat}`).join('|');
    const changed = dimension !== appliedMode;
    if (changed) { map.setTerrain(dimension === '3d' ? { source: 'elevation', exaggeration: 1.4 } : null); appliedMode = dimension; }
    if (key !== boundsKey) { boundsKey = key; fit(current); }
    else if (changed) map.easeTo({ pitch: dimension === '3d' ? 65 : 0, bearing: dimension === '3d' ? -18 : 0, duration: 600 });
  });
  $effect(() => {
    if (!ready || !map) return;
    map.setPaintProperty('land', 'raster-brightness-max', theme === 'dark' ? 0.55 : 1);
  });
  $effect(() => { if (retry && map) { tileFailure = false; map.triggerRepaint(); } });
  function fit(current = points) {
    if (!map || !current.length) return;
    const bounds = new library.LngLatBounds();
    current.forEach(p => bounds.extend([p.lon, p.lat]));
    map.fitBounds(bounds, { padding: 65, maxZoom: 12, duration: 700, pitch: mode === '3d' ? 65 : 0, bearing: mode === '3d' ? -18 : 0 });
  }
</script>

<div class="map-frame">
  <div bind:this={container} class="map-canvas" aria-label="Interactive map of passage locations"></div>
  {#if failure}<div class="map-notice">{failure}</div>
  {:else if !ready}<div class="map-notice">Opening the landscape…</div>{/if}
  {#if ready}<button class="map-fit" onclick={() => fit()}><Icon name="expand" />Fit places</button>{/if}
  {#if tileFailure}<div class="tile-notice">Some map imagery could not load. Place coordinates remain available. <button onclick={() => retry++}>Dismiss</button></div>{/if}
  <div class="map-legend"><span>● Located site</span><span>◇ Alternative candidate</span>{#if mode === '3d'}<span>Elevation × 1.4</span>{/if}</div>
</div>
