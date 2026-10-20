<script>
  import { onMount } from 'svelte';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import mapWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
  import { getBasemap } from './imagery.js';
  import Icon from './Icon.svelte';
  let { points = [], theme = 'light', imagery = 'streets', selected = '', selectedCandidate = '', onSelect = () => {} } = $props();
  let container;
  let map;
  let library;
  let markers = [];
  let ready = $state(false);
  let failure = $state('');
  let tileFailure = $state('');
  let imageryRetry = $state(0);
  const basemap = $derived(getBasemap(imagery));
  let activeLayerIds = [];
  let activeImageryKey = '';
  let activeImageryLabel = '';
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
            sources: {},
            layers: [],
          },
        });
        map.addControl(new library.NavigationControl(), 'top-right');
        map.on('load', () => { if (!disposed) ready = true; });
        map.on('error', event => {
          if (!disposed && activeLayerIds.includes(event.sourceId)) {
            tileFailure = `${activeImageryLabel} imagery could not load completely. Choose another map style above, or retry.`;
          }
        });
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
    const definition = basemap;
    const key = `${definition.id}:${imageryRetry}`;
    const dark = theme === 'dark';
    if (key !== activeImageryKey) {
      // Remove sources as well as layers so inactive imagery stops requesting
      // tiles and its credit leaves the attribution control.
      for (const id of activeLayerIds) {
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
      }
      activeLayerIds = [];
      activeImageryKey = key;
      activeImageryLabel = definition.label;
      tileFailure = '';
      try {
        for (const layer of definition.layers) {
          const id = `imagery-${layer.id}`;
          activeLayerIds.push(id);
          map.addSource(id, {
            type: 'raster', tileSize: layer.tileSize, maxzoom: layer.maxZoom,
            tiles: [layer.url], attribution: layer.attribution,
          });
          map.addLayer({
            id, type: 'raster', source: id,
            paint: {
              'raster-saturation': layer.saturation ?? 0,
              'raster-brightness-max': dark ? (layer.darkBrightness ?? 1) : 1,
              'raster-fade-duration': 0,
            },
          });
        }
      } catch {
        tileFailure = `${definition.label} imagery could not start. Choose another map style above, or retry.`;
      }
    } else {
      for (const layer of definition.layers) {
        const id = `imagery-${layer.id}`;
        if (map.getLayer(id)) {
          map.setPaintProperty(id, 'raster-brightness-max', dark ? (layer.darkBrightness ?? 1) : 1);
        }
      }
    }
  });
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
  {#if tileFailure}<div class="tile-notice" role="status">{tileFailure} <button onclick={() => imageryRetry++}>Retry imagery</button></div>{/if}
  <div class="map-legend"><span>● Located site</span><span>◇ Alternative candidate</span></div>
</div>
