<script>
  import Icon from './Icon.svelte';
  import EntityLinks from './EntityLinks.svelte';
  import { json, lookupLemma, referenceLabel, nativeToEnglish, versePreview } from './data.js';

  let { catalog, book, chapter, verse, text, edition, verseMap, inverseMap, isSaved, openRequest = 0, onSave, onNavigate, onArticle, onMap, onResearch } = $props();
  let tab = $state('language');
  let words = $state([]);
  let sourceRefs = $state([]);
  let wordIndex = $state(-1);
  let lemma = $state(null);
  let occurrences = $state([]);
  let references = $state([]);
  let shown = $state(5);
  let loading = $state(false);
  let error = $state('');
  let lemmaError = $state('');
  let previewError = $state('');
  let previews = $state({});
  let mobileOpen = $state(false);
  let requestId = 0;
  let lemmaRequest = 0;
  let previewRequest = 0;
  const ref = $derived(`${book}.${chapter}.${verse}`);
  const language = $derived(book <= 39 ? 'hebrew' : 'greek');
  const word = $derived(words[wordIndex]);
  const eligible = $derived(book <= 66 && edition?.numbering === 'english');
  const cards = $derived(tab === 'references' ? references : occurrences);

  $effect(() => {
    const coordinates = [book, chapter, verse, edition?.id];
    if (coordinates[3]) {
      loadStudy(coordinates[0], coordinates[1], coordinates[2], coordinates[3]);
    }
  });
  $effect(() => {
    if (openRequest && window.matchMedia('(max-width:650px)').matches) mobileOpen = true;
  });

  async function loadStudy(b, c, v, editionId) {
    const id = ++requestId;
    ++lemmaRequest;
    words = []; references = []; occurrences = []; lemma = null; wordIndex = -1;
    error = ''; lemmaError = ''; previewError = ''; shown = 5;
    if (b > 66 || catalog.translations.find(t => t.id === editionId)?.numbering !== 'english') return;
    loading = true;
    try {
      const current = `${b}.${c}.${v}`;
      const originals = b <= 39 ? (verseMap[current] || [current]) : [current];
      const [originalData, crossrefs] = await Promise.all([
        Promise.all(originals.map(async original => {
          const [ob, oc, ov] = original.split('.');
          const data = await json(`/data/original/${ob}/${oc}.json`);
          return data[ov] || [];
        })),
        json(`/data/crossrefs/${b}.json`)
      ]);
      if (id !== requestId) return;
      words = originalData.flat();
      sourceRefs = originals;
      references = crossrefs[current] || [];
      const preferred = words.findIndex(w => /^(λόγος|רֵאשִׁית)$/.test(w.lemma));
      const fallback = words.findIndex(w => w.pos === 'noun' || w.pos === 'verb');
      const index = preferred >= 0 ? preferred : fallback >= 0 ? fallback : 0;
      if (words.length) selectWord(index);
    } catch (e) {
      if (id === requestId) error = 'The study data could not be loaded. Check your connection and try again.';
    } finally {
      if (id === requestId) loading = false;
    }
  }

  async function selectWord(index) {
    wordIndex = index;
    lemma = null; occurrences = []; shown = 5; lemmaError = '';
    const id = ++lemmaRequest;
    const w = words[index];
    if (!w?.lemma) return;
    try {
      const result = await lookupLemma(w.lemma, language);
      if (id !== lemmaRequest) return;
      lemma = result;
      const seen = new Set();
      occurrences = (result?.refs || []).flatMap(original => {
        const englishRefs = language === 'hebrew' ? nativeToEnglish(original, inverseMap) : [original];
        return englishRefs.filter(r => {
          if (r === ref || seen.has(r) || r.endsWith('.0')) return false;
          seen.add(r); return true;
        }).map(r => ({ ref: r, original, end: null }));
      });
    } catch {
      if (id === lemmaRequest) lemmaError = 'The concordance could not be loaded. Select the word again to retry.';
    }
  }

  $effect(() => {
    const visible = cards.slice(0, shown);
    const editionId = edition?.id;
    if (editionId) loadPreviews(visible, editionId);
  });

  async function loadPreviews(visible, editionId) {
    const id = ++previewRequest;
    previews = {}; previewError = '';
    try {
      const results = await Promise.all(visible.map(async card => [card.ref, await versePreview(card.ref, editionId)]));
      if (id === previewRequest) previews = Object.fromEntries(results);
    } catch {
      if (id === previewRequest) previewError = 'Some previews could not load. You can still open the references.';
    }
  }

  function changeTab(value) { tab = value; shown = 5; }
  function openReference(target) { mobileOpen = false; onNavigate(target); }
  function label(target) { return referenceLabel(target, catalog.books); }
  function rangeLabel(card) {
    if (!card.end) return label(card.ref);
    const start = card.ref.split('.');
    const end = card.end.split('.');
    return `${label(card.ref)}–${start[0] === end[0] && start[1] === end[1] ? end[2] : label(card.end)}`;
  }
</script>

<aside class:mobile-active={mobileOpen} class="study-pane" aria-label="Verse study">
  {#if mobileOpen}<button class="icon-button mobile-study-close" aria-label="Close verse study" onclick={() => mobileOpen = false}><Icon name="x" /></button>{/if}
  <div class="study-topline"><span class="eyebrow">VERSE STUDY</span></div>
  <div class="study-title-row"><h2>{label(ref)}</h2><button class:is-saved={isSaved} class="icon-button" aria-label={isSaved ? 'Unsave selected verse' : 'Save selected verse'} aria-pressed={isSaved} onclick={onSave}><Icon name="bookmark" /></button></div>
  <blockquote>{text || 'Select a verse to begin exploring.'}</blockquote>
  <EntityLinks {book} {chapter} {verse} {text} gloss={word?.gloss || ''} aligned={eligible} {onArticle} {onMap} />
  <button class="study-research-button" onclick={onResearch}><Icon name="spark" />Compare interpretations<Icon name="arrow-right" /></button>
  <div class="study-tabs" role="tablist" aria-label="Study tools">
    {#each [['language', 'Original language'], ['references', 'Cross-references']] as [value, title]}
      <button role="tab" id={`${value}-tab`} aria-selected={tab === value} aria-controls="study-content" tabindex={tab === value ? 0 : -1} onclick={() => changeTab(value)} onkeydown={event => {
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); changeTab(value === 'language' ? 'references' : 'language'); document.getElementById(`${tab}-tab`)?.focus(); }
      }}>{title}</button>
    {/each}
  </div>
  <div id="study-content" role="tabpanel" aria-labelledby={`${tab}-tab`}>
    {#if !eligible}
      <p class="empty-note">{book > 66 ? 'The downloaded original-language datasets cover the Hebrew Bible and Greek New Testament. Original texts for this book are not yet installed.' : 'This edition uses its own verse numbering. Automatic language alignment and cross-references are available in the English-numbered editions.'}</p>
      {#if book <= 66}<button class="subtle-button" onclick={() => onNavigate(`${book}.1.1`, 'BSB')}>Open this book in BSB <Icon name="arrow-right" /></button>{/if}
    {:else if loading}
      <p class="loading">Opening the source texts…</p>
    {:else if error}
      <p class="error-note">{error} <button onclick={() => loadStudy(book, chapter, verse, edition.id)}>Retry</button></p>
    {:else}
      {#if tab === 'language'}
        <div class="section-label">{language === 'hebrew' ? 'HEBREW & ARAMAIC TEXT' : 'GREEK TEXT'}<span class="language-badge">{language === 'hebrew' ? 'WLC' : 'SBLGNT'}</span></div>
        {#if words.length}
          <div class="original-words" dir={language === 'hebrew' ? 'rtl' : 'ltr'}>
            {#each words as w, index}
              <button class="word-button" class:selected={wordIndex === index} onclick={() => selectWord(index)} aria-label={`${w.text}, ${w.gloss}; explore lemma ${w.lemma}`} aria-pressed={wordIndex === index}>
                <span class="word-text" lang={w.language === 'A' ? 'arc' : language === 'hebrew' ? 'he' : 'grc'}>{w.text}</span><span class="word-gloss">{w.gloss}</span>
              </button>
            {/each}
          </div>
          <p class="source-caption">Select a {language === 'hebrew' ? 'word or prefix' : 'word'} to trace its lemma through Scripture.{#if sourceRefs.some(r => r !== ref)}<br>Source numbering: {sourceRefs.map(label).join(', ')}.{/if}</p>
          {#if word}
            <div class="word-card">
              <div class="word-card-heading"><span class="lemma-title" dir={language === 'hebrew' ? 'rtl' : 'ltr'} lang={language === 'hebrew' ? 'he' : 'grc'}>{word.lemma || word.text}</span><span class="strong-tag">{word.strong || word.pos}</span></div>
              {#if word.transliteration}<div class="word-transliteration">{word.transliteration}</div>{/if}
              <p class="word-definition">{word.gloss || 'No contextual gloss available.'}</p>
              <div class="word-grammar"><b>{word.pos}</b> · {word.morph}{#if word.grammar}<br>{word.grammar}{/if}</div>
            </div>
          {/if}
          <div class="section-label">THE SAME LEMMA<span class="lemma-count">{lemma ? `${lemma.count.toLocaleString()} occurrences` : '…'}</span></div>
          <p class="source-caption">Lexical connections in {language === 'hebrew' ? 'the WLC' : 'the SBLGNT'}. Context and meaning can differ.</p>
          {#if lemmaError}<p class="error-note">{lemmaError}</p>{/if}
        {:else}
          <p class="empty-note">This verse is not represented in the selected source text. Critical Greek editions and English translations can include different readings.</p>
        {/if}
      {:else}
        <div class="section-label">CONNECTED PASSAGES<span class="lemma-count">{references.length} references</span></div>
        <p class="source-caption">Community-ranked connections from <a href="https://www.openbible.info/labs/cross-references/" target="_blank" rel="noreferrer">OpenBible.info</a>.</p>
      {/if}
      {#if previewError}<p class="error-note">{previewError}</p>{/if}
      {#each cards.slice(0, shown) as card (card.ref + (card.end || ''))}
        <button class="reference-card" onclick={() => openReference(card.ref)}>
          <span class="reference-top">{rangeLabel(card)}<Icon name="arrow-up-right" /></span>
          <p>{previews[card.ref] || 'Loading passage…'}</p>
          {#if card.end}<p class="reference-note">Preview of the first verse in this range.</p>{/if}
          {#if card.original && card.original !== card.ref}<p class="reference-note">Hebrew numbering: {label(card.original)}</p>{/if}
        </button>
      {/each}
      {#if cards.length > shown}<button class="load-more" onclick={() => shown += 10}>Show more connections ({cards.length - shown})</button>
      {:else if !cards.length && (tab === 'references' || lemma)}<p class="empty-note">No additional passages in this dataset.</p>{/if}
      <p class="source-caption attribution-caption">MACULA {language === 'hebrew' ? 'Hebrew' : 'Greek'} Linguistic Datasets · CC BY 4.0<br>{language === 'hebrew' ? 'WLC · Open Scriptures · Cherith glosses' : 'SBLGNT · Berean interlinear glosses'}</p>
    {/if}
  </div>
</aside>
