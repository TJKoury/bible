<script>
  import { basemaps, savedImagery } from './imagery.js';
  import { storageWrite } from './data.js';
  let { mode = $bindable('2d'), reconstruction = $bindable(false), imagery = $bindable(savedImagery()), scope = $bindable(null), verse = 1 } = $props();
</script>

<div class="map-toolbar" aria-label="Map controls">
  <div class="map-toolbar-scope">
    {#if scope !== null}
      <div class="segmented" role="group" aria-label="Map passage scope">
        {#each ['chapter', 'verse'] as s}<button class:active={scope === s} aria-pressed={scope === s} onclick={() => scope = s}>{s === 'chapter' ? 'Whole chapter' : `Verse ${verse}`}</button>{/each}
      </div>
    {/if}
  </div>
  <div class="segmented map-mode" role="group" aria-label="Map dimensions">
    <button class:active={mode === '2d'} aria-pressed={mode === '2d'} onclick={() => mode = '2d'}>2D map</button>
    <button class:active={mode === '3d'} aria-pressed={mode === '3d'} onclick={() => mode = '3d'}>Cesium 3D</button>
  </div>
  <div class="map-toolbar-settings">
    {#if mode === '3d'}
      <select aria-label="Landscape view" value={reconstruction ? 'reconstruction' : 'modern'} onchange={event => reconstruction = event.currentTarget.value === 'reconstruction'}>
        <option value="modern">Modern landscape</option>
        <option value="reconstruction">Reconstruction lab</option>
      </select>
    {/if}
    <label>Imagery
      <select aria-label="Map imagery" bind:value={imagery} disabled={mode === '3d' && reconstruction} onchange={event => storageWrite('scripture-map-imagery', event.currentTarget.value)} title={mode === '3d' && reconstruction ? 'Modern imagery is hidden in the reconstruction lab.' : 'Choose a map layer'}>
        {#each basemaps as map}<option value={map.id}>{map.label}</option>{/each}
      </select>
    </label>
  </div>
</div>
