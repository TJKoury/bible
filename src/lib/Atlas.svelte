<script>
  import { onMount } from 'svelte';
  import Icon from './Icon.svelte';
  import MapView from './MapView.svelte';
  import { json, referenceLabel } from './data.js';
  import { passagePlaces, mapPoints, candidateKey } from './geography.js';
  let { catalog, book, chapter, verse, edition, theme, onPassage, onArticle } = $props();
  let data = $state(null);
  let error = $state('');
  let scope = $state('chapter');
  let mode = $state('2d');
  let selected = $state('');
  let selectedCandidate = $state('');
  let requested = $state('');
  let filter = $state('');
  const aligned = $derived(edition?.numbering === 'english' && book <= 66);
  const places = $derived(aligned ? passagePlaces(data, book, chapter, verse, scope) : []);
  const shownPlaces = $derived(filter.trim() ? Object.values(data?.places || {}).filter(p => `${p.name} ${(p.aliases || []).join(' ')}`.toLowerCase().includes(filter.toLowerCase())).slice(0, 40) : places);
  const focusedPlaces = $derived(selected ? shownPlaces.filter(p => p.id === selected) : shownPlaces);
  const points = $derived(mapPoints(focusedPlaces));
  const currentPlace = $derived(shownPlaces.find(p => p.id === selected));
  const currentBook = $derived(catalog.books.find(b => b.id === book));
  const chapters = $derived(edition.books.find(b => b.id === book)?.chapters || []);
  $effect(() => { const target = `${book}.${chapter}.${verse}.${scope}`; if (target !== requested) { requested = target; clearSelection(); filter = ''; } });
  onMount(load);
  async function load() { try { error = ''; data = await json('/data/geography/index.json'); } catch { error = 'The atlas data could not load.'; } }
  function title(ref) { return referenceLabel(ref, catalog.books); }
  function clearSelection() { selected = ''; selectedCandidate = ''; }
  function selectPlace(id) { selected = selected === id ? '' : id; selectedCandidate = ''; }
  function selectCandidate(placeId, key) { selected = placeId; selectedCandidate = key; }
</script>

<section class="explore-view atlas-view">
  <div class="explore-heading"><h1>Geography & maps</h1></div>
  <div class="context-toolbar">
    <div class="segmented" role="group" aria-label="Map passage scope">{#each ['chapter', 'verse'] as s}<button class:active={scope === s} aria-pressed={scope === s} onclick={() => scope = s}>{s === 'chapter' ? 'Whole chapter' : `Verse ${verse}`}</button>{/each}</div>
    <div class="segmented map-mode" role="group" aria-label="Map dimensions"><button class:active={mode === '2d'} aria-pressed={mode === '2d'} onclick={() => mode = '2d'}>2D map</button><button class:active={mode === '3d'} aria-pressed={mode === '3d'} onclick={() => mode = '3d'}>Cesium 3D</button></div>
  </div>
  {#if error}<p class="error-note">{error} <button onclick={load}>Retry</button></p>{/if}
  <div class="atlas-layout">
    <div class="atlas-main">
      <MapView {points} {mode} {theme} {selected} {selectedCandidate} onSelect={selectCandidate} />
      <p class="source-caption">Modern terrain; dated historical evidence is available in the reconstruction lab where sourced. Online tiles: OpenStreetMap · <a href="https://mapterhorn.com/attribution/" target="_blank" rel="noreferrer">Mapterhorn elevation</a>. Locations: <a href="https://www.openbible.info/geo/" target="_blank" rel="noreferrer">OpenBible.info · CC BY 4.0</a>.</p>
      {#if currentPlace}
        <div class="atlas-detail">
          <p class="eyebrow">PLACE RECORD</p><h2>{currentPlace.name}</h2>
          <p>{currentPlace.comment || 'Read the source record for the evidence behind these identifications.'}</p>
          <div class="inline-actions">{#if currentPlace.articleId}<button class="primary-button" onclick={() => onArticle(currentPlace.articleId)}>Open study encyclopedia<Icon name="arrow-right" /></button>{/if}<a class="subtle-button" href={currentPlace.url} target="_blank" rel="noreferrer">Location sources ↗</a></div>
          <div class="candidate-grid">{#each currentPlace.candidates || [] as candidate, index}<div class="candidate-card" class:active={selectedCandidate === candidateKey(currentPlace.id, candidate, index)}><span class="outline-badge">{currentPlace.candidates.length > 1 ? 'Candidate identification' : 'Source identification'}</span><h3>{candidate.name}</h3><p>{candidate.description || candidate.kind || 'See the source for identification evidence.'}</p>{#if Number.isFinite(candidate.lat) && Number.isFinite(candidate.lon)}<code>{candidate.lat.toFixed(4)}°, {candidate.lon.toFixed(4)}°</code>{:else}<p>Coordinates unknown.</p>{/if}</div>{/each}</div>
          <p class="source-caption">Multiple candidates are alternatives, not stops along a journey. A mapped point can represent a wider region. Source rankings are not probabilities.</p>
        </div>
      {/if}
    </div>
    <aside class="atlas-places" aria-label="Places in passage">
      <div class="section-label">{filter ? 'ATLAS SEARCH' : `${currentBook?.name} ${chapter}${scope === 'verse' ? `:${verse}` : ''}`}<span>{shownPlaces.length} places</span></div>
      <label class="field-search"><Icon name="search" /><input aria-label="Search all atlas places" bind:value={filter} oninput={clearSelection} placeholder="Search the whole atlas" /></label>
      {#if selected}<button class="text-button" onclick={clearSelection}>Show all matching places</button>{/if}
      {#if !aligned}<p class="empty-note">Passage maps use English verse numbering. Choose BSB, WEB, or KJV in the reader to align this passage.</p>
      {:else if data && !shownPlaces.length}<div class="empty-note"><Icon name="map" /><p>No locations are indexed for this {scope}. Search the atlas to explore a place; the app does not invent a location for the passage.</p></div>{/if}
      {#each shownPlaces as place (place.id)}
        <div class="place-entry">
        <button class="place-row" class:active={selected === place.id} aria-expanded={place.candidates?.length > 1 ? selected === place.id : undefined} aria-controls={place.candidates?.length > 1 ? `candidates-${place.id}` : undefined} aria-pressed={place.candidates?.length > 1 ? undefined : selected === place.id} onclick={() => selectPlace(place.id)}>
          <Icon name="pin" /><span><strong>{place.name}</strong><small>{place.candidates?.length || 0} {place.candidates?.length === 1 ? 'identification' : 'candidate identifications'}</small><small>{(place.refs || []).filter(r => r.startsWith(`${book}.${chapter}.`)).slice(0, 4).map(title).join(' · ')}</small></span><Icon name="chevron-right" />
        </button>
        {#if place.candidates?.length > 1}
          <div class="place-candidates" id={`candidates-${place.id}`} role="group" aria-label={`${place.name} candidate locations`} hidden={selected !== place.id}>
            {#each place.candidates as candidate, index}
              {@const key = candidateKey(place.id, candidate, index)}
              <button class="candidate-row" class:active={selectedCandidate === key} aria-pressed={selectedCandidate === key} onclick={() => selectCandidate(place.id, key)}>
                <Icon name={selectedCandidate === key ? 'check' : 'pin'} size={15} />
                <span><strong>{candidate.name || 'Unnamed candidate'}</strong><small>{#if Number.isFinite(candidate.lat) && Number.isFinite(candidate.lon)}{candidate.lat.toFixed(4)}°, {candidate.lon.toFixed(4)}°{:else}Coordinates unknown{/if}</small></span>
              </button>
            {/each}
          </div>
        {/if}
        </div>
      {/each}
      <p class="source-caption">{data ? Object.keys(data.places).length.toLocaleString() : 'Loading'} place records. Geographic coverage does not imply a complete archaeological record.</p>
    </aside>
  </div>
</section>
