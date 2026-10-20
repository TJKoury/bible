<script>
  import { onMount } from 'svelte';
  import Icon from './Icon.svelte';
  import MapView from './MapView.svelte';
  import { json } from './data.js';
  import { articleList, linkedArticles, passagePlaces, mapPoints } from './geography.js';
  let { selectedId = '', book, chapter, verse, text, aligned, theme, onSelect, onMap, onResearch } = $props();
  let index = $state(null);
  let geography = $state(null);
  let article = $state(null);
  let query = $state('');
  let category = $state('all');
  let section = $state('overview');
  let error = $state('');
  let loading = $state(false);
  let mapMode = $state('2d');
  let loadId = 0;
  const sections = [['overview','Overview'],['archaeology','Archaeology'],['maps','Maps'],['artifacts','Artifacts'],['literature','Other literature'],['references','References']];
  const articles = $derived(articleList(index));
  const contextPlaces = $derived(aligned ? passagePlaces(geography, book, chapter, verse, 'chapter') : []);
  const inPassage = $derived(new Set([...contextPlaces.map(p => p.articleId).filter(Boolean), ...linkedArticles(index, text || '').map(a => a.id)]));
  const matches = $derived(articles.filter(a =>
    (category !== 'passage' || inPassage.has(a.id)) &&
    `${a.title} ${(a.aliases || []).join(' ')}`.toLowerCase().includes(query.toLowerCase())
  ).sort((a, b) => a.title.localeCompare(b.title)));
  const relatedPlaces = $derived(Object.values(geography?.places || {}).filter(p => p.articleId === article?.id || (article?.relatedPlaces || []).includes(p.id)));
  const points = $derived(mapPoints(relatedPlaces));
  const displayedSections = $derived((article?.sections || []).filter(s => section === 'overview' ? ['overview','history','other','geography','biography','religion','context'].includes(s.category) || !s.category : s.category === section));
  const notes = $derived((article?.notes || []).filter(n => section === 'overview' || n.category === section));
  onMount(loadIndex);
  async function loadIndex() {
    try { error = ''; [index, geography] = await Promise.all([json('/data/encyclopedia/index.json'), json('/data/geography/index.json')]); }
    catch { error = 'The encyclopedia index could not load. Please retry.'; }
  }
  $effect(() => { if (selectedId) loadArticle(selectedId); else { ++loadId; article = null; } });
  async function loadArticle(id) {
    const ticket = ++loadId;
    loading = true; error = ''; article = null; section = 'overview';
    try { const result = await json(`/data/encyclopedia/articles/${encodeURIComponent(id)}.json`); if (ticket === loadId) article = result; }
    catch { if (ticket === loadId) error = 'This article could not load. Please retry.'; }
    finally { if (ticket === loadId) loading = false; }
  }
  function safeUrl(value) {
    try { const url = new URL(value, 'https://en.wikipedia.org'); return /^https?:$/.test(url.protocol) ? url.href : null; } catch { return null; }
  }
</script>

<section class="explore-view encyclopedia-view">
  <div class="explore-heading"><div><p class="eyebrow">HISTORY, LANGUAGE & THE WORLD OF THE TEXT</p><h1>A study beyond the margins.</h1><p>Follow a name into its history. Keep the evidence in view.</p></div><span class="outline-badge"><Icon name="compass" />Study encyclopedia</span></div>
  <div class="encyclopedia-layout">
    <aside class="encyclopedia-directory" aria-label="Encyclopedia articles">
      <label class="field-search"><Icon name="search" /><input aria-label="Find encyclopedia article" bind:value={query} placeholder="Bethsaida, Moses, covenant…" /></label>
      <div class="segmented" role="group" aria-label="Article scope"><button class:active={category === 'all'} aria-pressed={category === 'all'} onclick={() => category = 'all'}>All articles</button><button class:active={category === 'passage'} aria-pressed={category === 'passage'} onclick={() => category = 'passage'}>This passage</button></div>
      <p class="source-caption">{matches.length.toLocaleString()} articles {query ? 'matching your search' : 'in this collection'}</p>
      <div class="article-list">{#each matches.slice(0, 120) as item}<button class:active={selectedId === item.id} onclick={() => onSelect(item.id)}><strong>{item.title}</strong><small>{item.kind || item.category || 'Encyclopedia'}</small><Icon name="chevron-right" /></button>{/each}</div>
      {#if matches.length > 120}<p class="source-caption">Showing the first 120. Search to narrow the list.</p>{/if}
      {#if index && !matches.length}<p class="empty-note">No matching article in the downloaded collection.</p><a class="subtle-button" href={`https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(query)}`} target="_blank" rel="noreferrer">Search Wikipedia ↗</a>{/if}
    </aside>
    <div class="encyclopedia-reader">
      {#if error}<p class="error-note">{error} <button onclick={() => selectedId ? loadArticle(selectedId) : loadIndex()}>Retry</button></p>
      {:else if loading}<p class="loading">Opening the study article…</p>
      {:else if article}
        <div class="article-header"><p class="eyebrow">{article.kind || 'STUDY ENCYCLOPEDIA'}</p><h2>{article.title}</h2><div class="article-provenance"><a href={article.revisionUrl || article.url} target="_blank" rel="noreferrer">Wikipedia source revision ↗</a><span>{article.license || 'CC BY-SA 4.0'}</span></div></div>
        {#if article.studyNotes?.status}<p class="coverage-note">{article.studyNotes.status}</p>{/if}
        {#if article.summary}<p class="article-lead">{article.summary}</p>{/if}
        <div class="article-tabs" role="group" aria-label="Study article sections">{#each sections as [id, title]}<button class:active={section === id} aria-pressed={section === id} onclick={() => section = id}>{title}</button>{/each}</div>
        {#if section === 'maps'}
          {#if points.length}<div class="inline-actions"><div class="segmented"><button class:active={mapMode === '2d'} onclick={() => mapMode = '2d'}>2D map</button><button class:active={mapMode === '3d'} onclick={() => mapMode = '3d'}>3D terrain</button></div><button class="subtle-button" onclick={onMap}>Open passage atlas <Icon name="arrow-right" /></button></div><MapView {points} mode={mapMode} {theme} />
            <p class="source-caption">Candidate identifications from OpenBible.info, CC BY 4.0. Modern landscape; alternative locations are not a reconstructed journey.</p>
            {#each relatedPlaces as place}<div class="article-section"><h3>{place.name}</h3>{#each place.candidates || [] as c}<p><strong>{c.name}</strong>{#if Number.isFinite(c.lat)} · {c.lat.toFixed(4)}°, {c.lon.toFixed(4)}°{/if}{#if c.description}<br>{c.description}{/if}</p>{/each}<a href={place.url} target="_blank" rel="noreferrer">Identification evidence ↗</a></div>{/each}
          {:else}<p class="empty-note">No geographical identification is linked to this article. People and ideas may not have a single meaningful map location.</p>{/if}
        {:else if section === 'references'}
          <div class="article-section"><h3>Verify the sources</h3><p>Wikipedia provides an overview and a path to further evidence. Its cited sources may disagree, and links do not imply permission to download their full text.</p>
            <div class="reference-links"><a href={article.revisionUrl || article.url} target="_blank" rel="noreferrer">Article revision used in this library ↗</a><a href={article.historyUrl || `${article.url}?action=history`} target="_blank" rel="noreferrer">Contributors & revision history ↗</a>
            {#each article.externalReferences || [] as reference}{@const url = safeUrl(typeof reference === 'string' ? reference : reference.url || reference.href)}{#if url}<a href={url} target="_blank" rel="noreferrer">{typeof reference === 'string' ? reference : reference.title || reference.text || url} ↗</a>{/if}{/each}</div>
          </div>
        {:else}
          {#each notes as note}<div class="evidence-note"><span class="outline-badge">Study note · source linked</span><h3>{note.title}</h3><p>{note.text}</p>{#if note.url}<a href={note.url} target="_blank" rel="noreferrer">Read the evidence ↗</a>{/if}</div>{/each}
          {#each displayedSections as part}<section class="article-section"><h3>{part.title || 'Background'}</h3>{#each part.text.split(/\n\s*\n/) as paragraph}<p>{paragraph}</p>{/each}{#if part.links?.length}<details><summary>Links in this section</summary><div class="reference-links">{#each part.links.slice(0, 15) as link}{@const url = safeUrl(typeof link === 'string' ? link : link.url || link.href)}{#if url}<a href={url} target="_blank" rel="noreferrer">{typeof link === 'string' ? link : link.title || link.text || url} ↗</a>{/if}{/each}</div></details>{/if}</section>{/each}
          {#if !displayedSections.length && !notes.length}<div class="empty-note"><h3>This section needs more evidence.</h3><p>No {section === 'literature' ? 'references in other literature' : section} section has been indexed for this article. That does not mean none exists.</p><a href={article.url} target="_blank" rel="noreferrer">Continue with the source article ↗</a></div>{/if}
        {/if}
        <div class="article-footer"><button class="subtle-button" onclick={() => onResearch(`What is known about ${article.title}, and which identifications or interpretations are disputed?`)}><Icon name="spark" />Research this topic</button><p>Adapted and abridged from Wikipedia contributors. <a href={article.historyUrl} target="_blank" rel="noreferrer">Attribution history</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer">CC BY-SA 4.0</a>. Separately labeled study notes: CC BY 4.0. Section grouping is editorial; source claims have not all been independently verified. {#if article.truncated || article.abridged}This article is abridged; consult the source for omitted material.{/if}</p></div>
      {:else}
        <div class="encyclopedia-welcome"><span class="large-symbol">✦</span><h2>Every name opens a door.</h2><p>Choose a person, place, or subject to explore its history, archaeology, artifacts, maps, and references in other literature.</p><div class="suggested-topics">{#each ['Bethsaida','Jerusalem','Moses','Abraham'] as title}{@const item = articles.find(a => a.title === title)}{#if item}<button onclick={() => onSelect(item.id)}>{title}<Icon name="arrow-up-right" /></button>{/if}{/each}</div><p class="source-caption">A growing, attributed collection—not an exhaustive scholarly encyclopedia. Coverage and missing sections are shown explicitly.</p></div>
      {/if}
    </div>
  </div>
</section>
