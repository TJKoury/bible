<script>
  import { onMount } from 'svelte';
  import Map2D from './Map2D.svelte';
  import CesiumView from './CesiumView.svelte';
  import { json } from './data.js';
  let { points = [], mode = '2d', theme = 'light', selected = '', selectedCandidate = '', onSelect = () => {} } = $props();
  let index = $state(null), studies = $state([]), studyError = $state('');
  let reconstruction = $state(false), periodId = $state(''), showEvidence = $state(true);
  let useThreshold = $state(false), threshold = $state(-209);
  let request = 0;
  const placeIds = $derived([...new Set(points.map(p=>p.placeId))]);
  const relevantStudies = $derived((index?.studies || []).filter(s=>s.placeIds.some(id=>placeIds.includes(id))));
  const periods = $derived([...new Map(studies.flatMap(s=>s.periods).map(p=>[p.id,p])).values()]);
  const effectivePeriod = $derived(periods.find(p=>p.id===periodId) || periods[0]);
  const sites = $derived(studies.flatMap(s=>s.sites || []).filter(s=>s.periodIds.includes(effectivePeriod?.id)));
  const claims = $derived(studies.flatMap(s=>(s.claims || []).map(c=>({...c,sources:s.sources.filter(source=>c.sourceIds.includes(source.id))}))).filter(c=>c.periodIds.includes(effectivePeriod?.id)));
  const waterLevels = $derived(studies.flatMap(s=>s.waterLevelAlternatives || []).filter(w=>w.periodIds.includes(effectivePeriod?.id)));
  const covered = $derived(placeIds.filter(id=>index?.places?.[id]?.studyIds?.length).length);
  onMount(() => { json('/data/reconstructions/index.json').then(data=>index=data).catch(()=>studyError='Historical evidence coverage could not load.'); });
  $effect(() => {
    const entries = relevantStudies;
    const ticket = ++request;
    studies=[];useThreshold=false;studyError='';
    Promise.all(entries.map(s=>json(s.path))).then(data=>{if(ticket===request)studies=data;}).catch(()=>{if(ticket===request)studyError='A historical evidence study could not load.';});
  });
</script>
{#if mode === '3d'}
  <div class="landscape-toolbar">
    <div class="segmented" role="group" aria-label="Landscape view">
      <button class:active={!reconstruction} aria-pressed={!reconstruction} onclick={()=>{reconstruction=false;useThreshold=false;}}>Modern landscape</button>
      <button class:active={reconstruction} aria-pressed={reconstruction} onclick={()=>reconstruction=true}>Reconstruction lab</button>
    </div>
    {#if reconstruction && periods.length}<label>Evidence period <select aria-label="Historical evidence period" value={effectivePeriod?.id} onchange={e=>{periodId=e.currentTarget.value;useThreshold=false;}}>{#each periods as p}<option value={p.id}>{p.label}</option>{/each}</select></label>{/if}
  </div>
  <CesiumView {points} {theme} {selected} {selectedCandidate} {onSelect} {reconstruction} evidenceSites={sites} {showEvidence} threshold={useThreshold && reconstruction ? Number(threshold) : null} />
  {#if reconstruction}
    <section class="reconstruction-evidence">
      <div class="section-label">Reconstruction coverage <span>{covered} of {placeIds.length} place records have dated evidence studies</span></div>
      <p>Modern terrain with ancient place identifications. Modern roads and labels are hidden. A dated shoreline, river course, or building reconstruction is shown only when a sourced geometry is available.</p>
      {#if studyError}<p class="error-note">{studyError}</p>{/if}
      {#if !studies.length}
        <p class="empty-note">No dated landscape geometry has been imported for these places. The terrain view works throughout the atlas; it does not imply that the ancient ground surface is known.</p>
      {:else}
        <label class="reconstruction-toggle"><input type="checkbox" bind:checked={showEvidence} />Show evidence locations for this period</label>
        {#each claims as claim}<div class="reconstruction-claim"><p>{claim.text}</p><small>{claim.evidenceType} · {claim.uncertainty}</small>{#each claim.sources as source}<a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a>{/each}</div>{/each}
        {#if waterLevels.length}
          <details class="height-experiment"><summary>Lake-level hypotheses and elevation experiment</summary>
            {#each waterLevels as water}<p><strong>{water.label}</strong><br>{water.applicability} {water.datum}</p>{/each}
            <p>The blue shading below is an uncalibrated height experiment on the modern elevation grid. It is not a reconstructed shoreline or a flood simulation. Sedimentation, bathymetry, drainage, and vertical-datum corrections are missing.</p>
            <label class="reconstruction-toggle"><input type="checkbox" bind:checked={useThreshold} />Enable illustrative elevation screening</label>
            {#if useThreshold}<label>Grid-height threshold: {Number(threshold).toFixed(1)} m<input aria-label="Illustrative grid-height threshold" type="range" min="-215" max="-200" step="0.1" bind:value={threshold} /></label>{/if}
          </details>
        {/if}
      {/if}
      <p class="source-caption">The evidence registry covers all {index?.meta?.placeCount || Object.keys(index?.places || {}).length} atlas places. Missing historical geometry is a data gap, not a flat or empty ancient landscape.</p>
    </section>
  {/if}
{:else}
  <Map2D {points} {theme} {selected} {selectedCandidate} {onSelect} />
{/if}
