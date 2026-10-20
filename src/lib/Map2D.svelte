<script>
  import { onMount } from 'svelte';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import mapWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
  import Icon from './Icon.svelte';
  let { points = [], theme = 'light', selected = '', selectedCandidate = '', onSelect = () => {} } = $props();
  let container;
  let map;
  let library;
  let markers = [];
  let ready = $state(false);
  let failure = $state('');
  let tileFailure = $state(false);
  let retry = $state(0);
  let boundsKey = null;
  let focusKey = '';
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
          center: [35.5, 32], zoom: 6, maxZoom: 16, maxPitch: 0,
          attributionControl: { compact: false },
          style: {
            version: 8,
            sources: {
              land: {
                type: 'raster', tileSize: 256, maxzoom: 19,
                tiles: [import.meta.env.VITE_MAP_TILES || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
              },
            },
            layers: [{ id: 'land', type: 'raster', source: 'land', paint: { 'raster-saturation': -0.55 } }],
          },
        });
        map.addControl(new library.NavigationControl(), 'top-right');
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
    const loaded = ready; const current = points; const chosen = selected; const chosenCandidate = selectedCandidate;
    if (!loaded || !map) return;
    markers.forEach(marker => marker.remove()); markers = [];
    for (const point of current) {
      const element = document.createElement('button');
      const highlighted = chosenCandidate ? chosenCandidate === point.key : chosen === point.placeId;
      element.className = `atlas-pin ${point.disputed ? 'candidate' : ''} ${highlighted ? 'chosen' : ''}`;
      element.setAttribute('aria-label', point.label);
      element.setAttribute('aria-pressed', String(highlighted));
      element.title = point.label;
      element.textContent = point.disputed ? '◇' : '●';
      element.onclick = () => onSelect(point.placeId, point.key);
      markers.push(new library.Marker({ element }).setLngLat([point.lon, point.lat]).addTo(map));
    }
    const key = current.map(p => `${p.key}:${p.lon}:${p.lat}`).join('|');
    const focused = current.find(point => point.key === chosenCandidate);
    const nextFocusKey = focused ? `${focused.key}:${focused.lon}:${focused.lat}` : '';
    if (focused && (nextFocusKey !== focusKey || key !== boundsKey)) {
      map.flyTo({ center: [focused.lon, focused.lat], zoom: Math.max(map.getZoom(), 12), duration: 700 });
    } else if (key !== boundsKey) {
      fit(current);
    }
    boundsKey = key;
    focusKey = nextFocusKey;
  });
  $effect(() => {
    if (!ready || !map) return;
    map.setPaintProperty('land', 'raster-brightness-max', theme === 'dark' ? 0.55 : 1);
  });
  $effect(() => { if (retry && map) { tileFailure = false; map.triggerRepaint(); } });
  function fit(current = points) {
    if (!map) return;
    if (!current.length) { map.easeTo({center:[35.5,32],zoom:5,pitch:0,bearing:0,duration:600});return; }
    const bounds = new library.LngLatBounds();
    current.forEach(p => bounds.extend([p.lon, p.lat]));
    map.fitBounds(bounds, { padding: 65, maxZoom: 12, duration: 700, pitch: 0, bearing: 0 });
  }
</script>

<div class="map-frame">
  <div bind:this={container} class="map-canvas" aria-label="Interactive map of passage locations"></div>
  {#if failure}<div class="map-notice">{failure}</div>
  {:else if !ready}<div class="map-notice">Opening the landscape…</div>{/if}
  {#if ready}<button class="map-fit" onclick={() => fit()}><Icon name="expand" />Fit places</button>{/if}
  {#if tileFailure}<div class="tile-notice">Some map imagery could not load. Place coordinates remain available. <button onclick={() => retry++}>Dismiss</button></div>{/if}
  <div class="map-legend"><span>● Located site</span><span>◇ Alternative candidate</span></div>
</div>
