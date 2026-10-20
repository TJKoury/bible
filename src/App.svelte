<script>
  import { onMount, tick } from 'svelte';
  import Icon from './lib/Icon.svelte';
  import StudyPanel from './lib/StudyPanel.svelte';
  import Atlas from './lib/Atlas.svelte';
  import Encyclopedia from './lib/Encyclopedia.svelte';
  import Research from './lib/Research.svelte';
  import { json, assetUrl, shortName, referenceLabel, parseReference, inverseMapping, storageRead, storageWrite } from './lib/data.js';

  let catalog = $state(null);
  let verseMap = $state({});
  let inverseMap = $state({});
  let translation = $state('BSB');
  let book = $state(43);
  let chapter = $state(1);
  let verse = $state(1);
  let bookText = $state({});
  let comparisonText = $state({});
  let compareTranslation = $state('KJV');
  let mode = $state('read');
  let view = $state('reader');
  let articleId = $state('');
  let researchStarted = $state(false);
  let researchRequest = $state(null);
  let articleAnchor = '';
  let testament = $state('NT');
  let sidebarOpen = $state(false);
  let focused = $state(false);
  let loading = $state(true);
  let loadedBook = $state('');
  let bootError = $state('');
  let passageError = $state('');
  let comparisonError = $state('');
  let saved = $state([]);
  let fontSize = $state(20);
  let theme = $state('light');
  let toast = $state('');
  let searchInput = $state('');
  let searchResults = $state([]);
  let searchStatus = $state('');
  let searching = $state(false);
  let searched = $state(false);
  let scrollToSelection = $state(false);
  let studyOpenRequest = $state(0);
  let searchDialog, settingsDialog, sourcesDialog, searchField;
  let passageRequest = 0, comparisonRequest = 0, searchRequest = 0, toastTimer;

  const edition = $derived(catalog?.translations.find(t => t.id === translation));
  const currentBook = $derived(catalog?.books.find(b => b.id === book));
  const bookMeta = $derived(edition?.books.find(b => b.id === book));
  const passageReady = $derived(loadedBook === `${translation}/${book}`);
  const verses = $derived(passageReady ? bookText[chapter] || {} : {});
  const selectedText = $derived(verses[verse] || '');
  const currentRef = $derived(`${book}.${chapter}.${verse}`);
  const availableBooks = $derived(catalog?.books.filter(b => edition?.books.some(item => item.id === b.id)) || []);
  const visibleBooks = $derived(availableBooks.filter(b => b.testament === testament));
  const isSaved = $derived(saved.some(item => item.ref === currentRef && item.edition === translation));
  const comparisonEditions = $derived(catalog?.translations.filter(t => t.numbering === 'english' && t.id !== translation) || []);
  const aligned = $derived(edition?.numbering === 'english');
  const readingContext = $derived({
    key:`${translation}/${currentRef}`, ref:currentRef, book,chapter,verse,
    label:referenceLabel(currentRef,catalog?.books || []),bookName:currentBook?.name,
    edition:translation,editionTitle:edition?.title,aligned,loading:loading || !passageReady,
    text:selectedText,
    passageText:Object.entries(verses).filter(([v])=>Math.abs(Number(v)-verse)<=3).map(([v,t])=>`${v} ${t}`).join(' '),
  });
  $effect(() => {
    const key = readingContext.key;
    if(key!==articleAnchor){articleAnchor=key;articleId='';}
  });

  onMount(() => {
    const position = storageRead('scripture-position', null);
    if (position) {
      translation = position.translation || 'BSB'; book = Number(position.book) || 43;
      chapter = Number(position.chapter) || 1; verse = Number(position.verse) || 1;
    }
    const preferences = storageRead('scripture-preferences', {});
    fontSize = Math.max(17, Math.min(27, Number(preferences.fontSize) || 20));
    theme = preferences.theme === 'dark' ? 'dark' : 'light';
    const bookmarks = storageRead('scripture-bookmarks', []);
    saved = Array.isArray(bookmarks) ? bookmarks.filter(s => s?.ref && s?.edition && typeof s.text === 'string') : [];
    boot();
    return () => clearTimeout(toastTimer);
  });

  async function boot() {
    bootError = '';
    try {
      const [library, mappings] = await Promise.all([json('/data/catalog.json'), json('/data/verse-map.json')]);
      verseMap = mappings; inverseMap = inverseMapping(mappings);
      catalog = library;
      if (!library.translations.some(t => t.id === translation)) translation = 'BSB';
      applyHash();
      normalizePosition();
    } catch {
      bootError = 'The library could not be loaded. Please retry.';
      loading = false;
    }
  }

  function normalizePosition() {
    const current = catalog.translations.find(t => t.id === translation);
    if (!current.books.some(b => b.id === book)) { book = current.books[0].id; chapter = 1; verse = 1; }
    const metadata = current.books.find(b => b.id === book);
    if (!metadata.chapters.includes(chapter)) { chapter = metadata.chapters[0]; verse = 1; }
    testament = catalog.books.find(b => b.id === book)?.testament || 'NT';
  }

  $effect(() => {
    const id = translation, bid = book, ready = catalog;
    if (ready) loadPassage(id, bid);
  });
  async function loadPassage(id, bid) {
    const request = ++passageRequest;
    loading = true; passageError = ''; bookText = {};
    try {
      const result = await json(`/data/translations/${id}/${bid}.json`);
      if (request !== passageRequest) return;
      bookText = result;
      loadedBook = `${id}/${bid}`;
      if (result[chapter] && !result[chapter][verse]) verse = Number(Object.keys(result[chapter])[0]);
    } catch {
      if (request === passageRequest) passageError = 'This passage could not load. Check your connection and retry.';
    } finally {
      if (request === passageRequest) loading = false;
    }
  }

  $effect(() => {
    if (!loading && Object.keys(verses).length && !(verse in verses)) {
      verse = Number(Object.keys(verses)[0]);
      persistPosition(false);
    }
  });
  $effect(() => {
    if (scrollToSelection && !loading && verse in verses) {
      scrollToSelection = false;
      tick().then(() => document.querySelector('.verse.selected')?.scrollIntoView({ block: 'center', behavior: 'instant' }));
    }
  });

  $effect(() => {
    const id = compareTranslation, bid = book, active = mode === 'compare', canAlign = aligned;
    if (active && canAlign) loadComparison(id, bid);
  });
  async function loadComparison(id, bid) {
    const request = ++comparisonRequest;
    comparisonError = ''; comparisonText = {};
    try {
      const result = await json(`/data/translations/${id}/${bid}.json`);
      if (request === comparisonRequest) comparisonText = result;
    } catch {
      if (request === comparisonRequest) comparisonError = 'The comparison translation could not load.';
    }
  }

  $effect(() => {
    document.body.dataset.theme = theme;
    document.body.classList.toggle('focus-mode', focused);
    document.documentElement.style.setProperty('--verse-size', `${fontSize}px`);
    storageWrite('scripture-preferences', { fontSize, theme });
  });

  function persistPosition(push = true) {
    storageWrite('scripture-position', { translation, book, chapter, verse });
    const hash = `#${translation}/${book}/${chapter}/${verse}`;
    if (location.hash !== hash) history[push ? 'pushState' : 'replaceState'](null, '', hash);
  }
  function applyHash() {
    const match = location.hash.match(/^#([A-Za-z0-9]+)\/(\d+)\/(\d+)\/(\d+)$/);
    if (!match || !catalog?.translations.some(t => t.id === match[1])) return;
    translation = match[1]; book = Number(match[2]); chapter = Number(match[3]); verse = Number(match[4]);
  }
  function onHistory() {
    if (!catalog) return;
    applyHash(); normalizePosition(); view = 'reader'; sidebarOpen = false;
  }
  function navigate(target, targetEdition = translation, scroll = true) {
    const [b, c, v] = target.split('.').map(Number);
    let nextEdition = catalog.translations.find(t => t.id === targetEdition);
    if (!nextEdition?.books.some(item => item.id === b)) {
      targetEdition = 'BSB'; nextEdition = catalog.translations.find(t => t.id === 'BSB');
      notify('Opened in BSB; this book is not in the selected edition.');
    }
    if (!nextEdition.books.some(item => item.id === b)) return;
    translation = targetEdition; book = b; chapter = c; verse = v;
    normalizePosition(); view = 'reader'; sidebarOpen = false; studyOpenRequest = 0;
    scrollToSelection = scroll && v > 1;
    persistPosition();
    searchDialog?.close();
    if (scroll) window.scrollTo({ top: 0, behavior: 'instant' });
  }
  function selectVerse(number) { verse = Number(number); studyOpenRequest++; persistPosition(); }
  function changeTranslation(id) {
    translation = id; normalizePosition();
    if (compareTranslation === id) compareTranslation = id === 'KJV' ? 'BSB' : 'KJV';
    persistPosition(); view = 'reader';
  }
  function adjacent(direction) {
    const index = bookMeta?.chapters.indexOf(chapter);
    if (index === undefined || index < 0) return null;
    const c = bookMeta.chapters[index + direction];
    if (c) return `${book}.${c}.1`;
    const nextBook = edition.books[edition.books.findIndex(item => item.id === book) + direction];
    if (!nextBook) return null;
    return `${nextBook.id}.${direction > 0 ? nextBook.chapters[0] : nextBook.chapters.at(-1)}.1`;
  }
  function moveChapter(direction) { const target = adjacent(direction); if (target) navigate(target); }
  function notify(message) {
    toast = message; clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast = '', 3300);
  }
  function toggleSaved() {
    if (!selectedText) return;
    if (isSaved) saved = saved.filter(item => !(item.ref === currentRef && item.edition === translation));
    else saved = [{ ref: currentRef, edition: translation, text: selectedText, date: new Date().toISOString() }, ...saved];
    notify(storageWrite('scripture-bookmarks', saved) ? 'Saved passages updated.' : 'Saved for this session; browser storage is unavailable.');
  }
  function removeSaved(item) {
    saved = saved.filter(s => !(s.ref === item.ref && s.edition === item.edition));
    storageWrite('scripture-bookmarks', saved);
  }
  function setView(value) { view = value; if (value === 'research') researchStarted = true; sidebarOpen = false; focused = false; window.scrollTo(0, 0); }
  function openArticle(id) { articleId = id; setView('encyclopedia'); }
  function openResearch(question = '') { researchRequest = { question, contextKey:readingContext.key }; setView('research'); }
  function atlasPassage(b, c, v) { navigate(`${b}.${c}.${v}`, translation, false); setView('atlas'); }
  function changeContext(b,c,v) { const currentView=view;navigate(`${b}.${c}.${v}`,translation,false);setView(currentView); }
  async function openSearch() { searchDialog.showModal(); await tick(); searchField.focus(); }
  function keyboard(event) {
    if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName) && !document.querySelector('dialog[open]')) {
      event.preventDefault(); openSearch();
    }
    if (event.key === 'Escape') sidebarOpen = false;
  }
  async function search(event) {
    event.preventDefault();
    const query = searchInput.trim();
    if (!query) return;
    const request = ++searchRequest;
    searched = true; searchResults = []; searchStatus = ''; searching = true;
    const activeTranslation = translation;
    const activeEdition = edition;
    const passage = parseReference(query, catalog.books);
    try {
      if (passage) {
        const metadata = activeEdition.books.find(b => b.id === passage.book);
        if (!metadata?.chapters.includes(passage.chapter)) {
          searchStatus = 'That book or chapter is not available in this edition.'; return;
        }
        const data = await json(`/data/translations/${activeTranslation}/${passage.book}.json`);
        if (request !== searchRequest) return;
        if (!data[passage.chapter]?.[passage.verse]) { searchStatus = 'That verse is not present in this chapter.'; return; }
        navigate(`${passage.book}.${passage.chapter}.${passage.verse}`, activeTranslation);
        return;
      }
      const phrase = query.replace(/^["“]|["”]$/g, '').toLocaleLowerCase();
      if (phrase.length < 2) { searchStatus = 'Enter at least two letters to search the text.'; return; }
      let total = 0;
      const results = [];
      for (let offset = 0; offset < activeEdition.books.length; offset += 8) {
        const batch = activeEdition.books.slice(offset, offset + 8);
        const chunks = await Promise.all(batch.map(async item => ({ id: item.id, data: await json(`/data/translations/${activeTranslation}/${item.id}.json`) })));
        if (request !== searchRequest) return;
        for (const chunk of chunks) {
          for (const [c, verses] of Object.entries(chunk.data)) {
            for (const [v, text] of Object.entries(verses)) {
              if (text.toLocaleLowerCase().includes(phrase)) {
                total++;
                if (results.length < 100) results.push({ ref: `${chunk.id}.${c}.${v}`, text, edition: activeTranslation });
              }
            }
          }
        }
        searchStatus = `Searching ${Math.min(offset + 8, activeEdition.books.length)} of ${activeEdition.books.length} books…`;
      }
      searchResults = results;
      searchStatus = `${total.toLocaleString()} matching verses in ${shortName(activeTranslation)}${total > 100 ? ' · showing the first 100' : ''}.`;
    } catch {
      if (request === searchRequest) searchStatus = 'Search could not finish downloading the text. Please try again.';
    } finally {
      if (request === searchRequest) searching = false;
    }
  }
  const publishers = [
    ['NIV', 'https://www.biblica.com/permissions/'],
    ['ESV', 'https://api.esv.org/'],
    ['NLT', 'https://www.tyndale.com/permissions'],
    ['NASB', 'https://www.lockman.org/permission-to-quote-copyright-trademark-information/'],
    ['NKJV', 'https://www.harpercollinschristian.com/permissions/'],
    ['CSB', 'https://csbible.com/about-the-csb/'],
    ['NRSVue', 'https://www.friendshippress.org/nrsvue'],
    ['NET', 'https://netbible.com/copyright/'],
  ];
  function label(ref) { return referenceLabel(ref, catalog?.books || []); }
</script>

<svelte:window onpopstate={onHistory} onkeydown={keyboard} />
<svelte:head><title>{currentBook ? `${currentBook.name} ${chapter} · ` : ''}Scripture</title></svelte:head>

<a class="skip-link" href="#passage">Skip to passage</a>
<header class="topbar">
  <button class="icon-button mobile-menu" aria-label="Toggle navigation" aria-expanded={sidebarOpen} onclick={() => sidebarOpen = !sidebarOpen}><Icon name="menu" /></button>
  <a class="brand" href={assetUrl('')} onclick={event => { event.preventDefault(); setView('reader'); }}><span class="brand-mark">s</span>scripture<span class="brand-period">.</span></a>
  {#if catalog}<button class="reading-anchor" onclick={()=>setView('reader')} title="Return to current passage">{readingContext.label}<span>{shortName(translation)}</span></button>{/if}
  <button class="search-trigger" aria-label="Find a passage or phrase" onclick={openSearch} disabled={!catalog}><Icon name="search" /><span>Find a passage or phrase</span><kbd>/</kbd></button>
  <button class="icon-button" aria-label="Reading appearance" onclick={() => settingsDialog.showModal()}><span class="aa">Aa</span></button>
  <button class="icon-button theme-toggle" aria-label={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'} title={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'} onclick={() => theme = theme === 'light' ? 'dark' : 'light'}><Icon name={theme === 'light' ? 'moon' : 'sun'} /></button>
</header>

{#if bootError}
  <div class="boot-error"><p>{bootError}</p><button class="subtle-button" onclick={boot}>Retry loading the library</button></div>
{:else if !catalog}
  <p class="loading boot-error">Opening your library…</p>
{:else}
  <div class="workspace">
    <aside class="sidebar" class:open={sidebarOpen} aria-label="Bible navigation">
      <nav class="main-nav" aria-label="Main navigation">
        {#each [['reader', 'Read & explore', 'book'], ['encyclopedia', 'Study encyclopedia', 'compass'], ['atlas', 'Geography & maps', 'map'], ['research', 'Research desk', 'spark'], ['library', 'Translation library', 'library'], ['saved', 'Saved passages', 'bookmark']] as [value, title, icon]}
          <button class="nav-item" class:active={view === value} aria-current={view === value ? 'page' : undefined} onclick={() => setView(value)}><Icon name={icon} />{title}{#if value === 'library' || value === 'saved'}<span class="nav-count">{value === 'library' ? catalog.translations.length : saved.length}</span>{/if}</button>
        {/each}
      </nav>
      <div class="sidebar-label">THE BOOKS<span>{availableBooks.length}</span></div>
      <div class="testament-tabs" role="group" aria-label="Testament">
        {#each [['OT', 'Old'], ['NT', 'New'], ['DC', 'Other']] as [value, title]}
          {#if availableBooks.some(b => b.testament === value)}<button class:active={testament === value} aria-pressed={testament === value} onclick={() => testament = value}>{title}</button>{/if}
        {/each}
      </div>
      <div class="book-list">
        {#each visibleBooks as item}
          <button class="book-button" class:active={book === item.id} onclick={() => navigate(`${item.id}.1.1`)} aria-current={book === item.id ? 'true' : undefined}>{item.name}{#if book === item.id}<span class="book-indicator"></span>{:else}<small>{edition.books.find(b => b.id === item.id)?.chapters.length}</small>{/if}</button>
        {/each}
      </div>
      <button class="sidebar-foot" onclick={() => sourcesDialog.showModal()}><span class="source-dot"></span>Sources & attribution<Icon name="arrow-up-right" /></button>
    </aside>
    <main class="main-content">
      {#if view !== 'reader'}
        <div class="shared-context" aria-label="Current reading context">
          <span>Reading</span>
          <select aria-label="Context book" value={book} onchange={e=>changeContext(Number(e.currentTarget.value),1,1)}>{#each availableBooks as item}<option value={item.id}>{item.name}</option>{/each}</select>
          <select aria-label="Context chapter" value={chapter} onchange={e=>changeContext(book,Number(e.currentTarget.value),1)}>{#each bookMeta?.chapters || [] as c}<option value={c}>Chapter {c}</option>{/each}</select>
          <select aria-label="Context verse" value={verse} onchange={e=>changeContext(book,chapter,Number(e.currentTarget.value))}>{#each Object.keys(verses) as v}<option value={Number(v)}>Verse {v}</option>{/each}</select>
          <span>{shortName(translation)}</span><button class="subtle-button" onclick={()=>setView('reader')}>Read passage<Icon name="arrow-right" /></button>
        </div>
      {/if}
      {#if view === 'reader'}
        <div class="reader-layout">
          <section class="reading-pane" aria-label="Scripture reader">
            <div class="passage-navigation"><div class="breadcrumb"><span>{currentBook?.testament === 'OT' ? 'Old Testament' : currentBook?.testament === 'NT' ? 'New Testament' : 'Additional books'}</span><span>/</span><span>{currentBook?.name}</span></div><button class="icon-button" aria-label="Toggle focused reading" aria-pressed={focused} onclick={() => focused = !focused}><Icon name="expand" /></button></div>
            <div class="chapter-heading">

              <div class="chapter-title-row"><h1>{currentBook?.name} <span>{chapter}</span></h1><div class="chapter-arrows"><button class="icon-button" aria-label="Previous chapter" disabled={!adjacent(-1)} onclick={() => moveChapter(-1)}><Icon name="chevron-left" /></button><button class="icon-button" aria-label="Next chapter" disabled={!adjacent(1)} onclick={() => moveChapter(1)}><Icon name="chevron-right" /></button></div></div>

            </div>
            <div class="reader-toolbar">
              <label class="select-wrap translation-select"><Icon name="globe" /><select aria-label="Bible translation" value={translation} onchange={event => changeTranslation(event.currentTarget.value)}>{#each catalog.translations as item}<option value={item.id}>{shortName(item.id)} · {item.title}</option>{/each}</select></label>
              <label class="select-wrap chapter-select"><select aria-label="Chapter" value={chapter} onchange={event => navigate(`${book}.${event.currentTarget.value}.1`)}>{#each bookMeta?.chapters || [] as c}<option value={c}>Chapter {c}</option>{/each}</select></label>
              <div class="segmented" role="group" aria-label="Reading mode">{#each ['read', 'compare'] as value}<button class:active={mode === value} aria-pressed={mode === value} onclick={() => mode = value}>{value === 'read' ? 'Read' : 'Compare'}</button>{/each}</div>
            </div>
            {#if mode === 'compare'}
              {#if aligned}<div class="compare-toolbar"><label>Compare with <select aria-label="Comparison translation" bind:value={compareTranslation}>{#each comparisonEditions as item}<option value={item.id}>{shortName(item.id)} · {item.title}</option>{/each}</select></label><span>English verse numbering</span></div>
              {:else}<p class="empty-note">Comparison is available for editions with English verse numbering. Switch to BSB, WEB, or KJV to compare.</p>{/if}
              {#if comparisonError}<p class="error-note">{comparisonError} <button onclick={() => loadComparison(compareTranslation, book)}>Retry</button></p>{/if}
            {/if}
            <div class="reading-hint"><Icon name="pointer" />Select a verse to explore its words and connections.</div>
            <article id="passage" class="passage" tabindex="-1" aria-label={`${currentBook?.name} ${chapter}`}>
              {#if loading}<p class="loading">Opening the passage…</p>
              {:else if passageError}<p class="error-note">{passageError} <button onclick={() => loadPassage(translation, book)}>Retry</button></p>
              {:else}
                {#each Object.entries(verses) as [number, text]}
                  <button class="verse" class:selected={verse === Number(number)} aria-label={`${currentBook?.name} ${chapter}:${number}. ${text}`} aria-pressed={verse === Number(number)} onclick={() => selectVerse(number)}>
                    <span class="verse-number">{number}</span><span class="verse-text">{#if text.trim()}{text}{:else}<span class="missing-verse">No verse text supplied at this reference in the downloaded source.</span>{/if}{#if mode === 'compare' && aligned}<span class="compare-text"><span class="compare-label">{shortName(compareTranslation)}</span>{comparisonText[chapter]?.[number] || (Object.keys(comparisonText).length ? 'No verse text at this reference in the source.' : 'Loading comparison…')}</span>{/if}</span>
                    {#if saved.some(s => s.ref === `${book}.${chapter}.${number}` && s.edition === translation)}<span class="saved-dot" aria-label="Saved">◆</span>{/if}
                  </button>
                {/each}
              {/if}
            </article>
            <div class="chapter-bottom"><span>{edition?.title} · {edition?.license}</span><button disabled={!adjacent(1)} onclick={() => moveChapter(1)}>Next chapter<Icon name="arrow-right" /></button></div>
          </section>
          <StudyPanel {catalog} {book} {chapter} {verse} text={selectedText} {edition} {verseMap} {inverseMap} {isSaved} openRequest={studyOpenRequest} onSave={toggleSaved} onNavigate={navigate} onArticle={openArticle} onMap={() => setView('atlas')} onResearch={() => openResearch(`Compare interpretations of ${label(currentRef)} across relevant traditions.`)} />
        </div>
      {:else if view === 'atlas'}
        <Atlas {catalog} {book} {chapter} {verse} {edition} {theme} onPassage={atlasPassage} onArticle={openArticle} />
      {:else if view === 'encyclopedia'}
        <Encyclopedia selectedId={articleId} {book} {chapter} {verse} text={selectedText} {aligned} {theme} contextLabel={readingContext.label} onSelect={openArticle} onMap={() => setView('atlas')} onResearch={openResearch} />
      {:else if view === 'library'}
        <section class="collection-view">
          <h1>Translation library</h1>
          <p class="collection-lead">Read, compare, and download editions with their source and license information.</p>
          <div class="library-stats"><div class="library-stat"><strong>{catalog.translations.length}</strong><span>English editions downloaded</span></div><div class="library-stat"><strong>2</strong><span>Original-language datasets</span></div><div class="library-stat"><strong>{Math.round(catalog.crossReferences / 1000)}k</strong><span>Verse cross-references</span></div></div>
          <div class="section-label">YOUR TRANSLATIONS<span>JSON DOWNLOADS · ZIP ARCHIVES</span></div>
          <div class="library-table">
            {#each catalog.translations as item}
              <div class="library-row"><span class="edition-monogram">{shortName(item.id)}</span><div class="edition-description"><h3>{item.title}</h3><p>{item.subtitle} · {item.books.length} books · {item.verses.toLocaleString()} verses<br>{item.license}{#if item.sourceGaps?.length} · {item.sourceGaps.length} source gaps noted in text{/if}</p></div><span class="installed"><Icon name="check" />Downloaded</span><button class="subtle-button" onclick={() => changeTranslation(item.id)}>Read<Icon name="arrow-right" /></button><a class="subtle-button" href={assetUrl(`/data/downloads/${item.id}.zip`)} download={`${item.id}.zip`} aria-label={`Download ${item.title}`}><Icon name="download" />ZIP</a></div>
            {/each}
          </div>
          <h2 class="collection-section-title">Original languages</h2>
          <div class="resource-grid">
            <div class="resource-card"><h3><span lang="he">בְּרֵאשִׁית</span> &nbsp; Hebrew & Aramaic</h3><p>Westminster Leningrad Codex with MACULA morphology, lemmas, transliteration, contextual glosses, and concordance data. Includes segmented prefixes and suffixes.</p><a class="subtle-button" href={assetUrl('/data/downloads/hebrew.zip')} download><Icon name="download" />Download study data</a></div>
            <div class="resource-card"><h3><span lang="grc">Ἐν ἀρχῇ</span> &nbsp; Greek</h3><p>SBL Greek New Testament with MACULA morphology, lemmas, contextual glosses, and concordance data. Follow each lemma through the entire New Testament.</p><a class="subtle-button" href={assetUrl('/data/downloads/greek.zip')} download><Icon name="download" />Download study data</a></div>
          </div>
          <h2 class="collection-section-title">Other major translations</h2>
          <p class="collection-lead">These editions are not installed. Full-text storage and redistribution require a suitable publisher license or authorized service. The links below lead to publisher information; no copyrighted text has been downloaded for these entries.</p>
          <div class="publisher-list">{#each publishers as [id, url]}<a href={url} target="_blank" rel="noreferrer">{id} ↗<span>Publisher access</span></a>{/each}</div>
          <p class="source-caption library-footnote">Downloaded editions are stored with this app. ZIP downloads contain JSON text and source metadata; they do not install an offline web app. <button class="text-button" onclick={() => sourcesDialog.showModal()}>View sources & attribution</button></p>
        </section>
      {:else if view === 'saved'}
        <section class="collection-view"><h1>Saved passages</h1><p class="collection-lead">Saved in this browser on this device.</p>
          {#if !saved.length}<div class="resource-card"><h3>No saved passages</h3><p>Select a verse in the reader and use the bookmark button to save it here.</p><button class="subtle-button" onclick={() => setView('reader')}>Back to reading<Icon name="arrow-right" /></button></div>{/if}
          {#each saved as item (item.ref + item.edition)}<div class="saved-card"><div class="saved-card-head"><button onclick={() => navigate(item.ref, item.edition)}>{label(item.ref)}<small>{shortName(item.edition)}</small></button><button class="icon-button" aria-label={`Remove ${label(item.ref)} from saved passages`} onclick={() => removeSaved(item)}><Icon name="trash" /></button></div><p>{item.text}</p></div>{/each}
        </section>
      {/if}
      {#if researchStarted}
        <div hidden={view !== 'research'}>
          <Research questionRequest={researchRequest} context={readingContext} active={view === 'research'} onNavigate={navigate} onArticle={openArticle} />
        </div>
      {/if}
    </main>
  </div>
{/if}

<dialog bind:this={searchDialog} class="search-dialog" onclose={() => { searchRequest++; searching = false; }}>
  <form id="search-form" onsubmit={search}><Icon name="search" /><input bind:this={searchField} bind:value={searchInput} autocomplete="off" placeholder="John 1:1, Psalm 23, or “in the beginning”" aria-label="Search passage or phrase" /><button class="icon-button" type="button" aria-label="Close search" onclick={() => searchDialog.close()}><Icon name="x" /></button></form>
  <div class="search-results" aria-live="polite">
    {#if !searched}<p>Enter a passage or search the full text of your selected translation.</p><div class="search-examples">{#each [['43.1.1', 'John 1'], ['19.23.1', 'Psalm 23'], ['1.1.1', 'Genesis 1']] as [ref, title]}<button onclick={() => navigate(ref)}>{title}</button>{/each}</div>
    {:else}<p>{searching && !searchStatus ? 'Searching the full text…' : searchStatus}</p>{#each searchResults as item}<button class="search-result" onclick={() => navigate(item.ref, item.edition)}><strong>{label(item.ref)}</strong><p>{item.text}</p></button>{/each}{/if}
  </div>
  <div class="search-footer"><span>{edition?.title || 'Scripture search'}</span><span><kbd>enter</kbd> to search <kbd>esc</kbd> to close</span></div>
</dialog>

<dialog bind:this={settingsDialog} class="small-dialog">
  <div class="dialog-heading"><h2>Reading appearance</h2><button class="icon-button" aria-label="Close appearance" onclick={() => settingsDialog.close()}><Icon name="x" /></button></div>
  <label class="setting-row" for="font-size">Text size<output>{fontSize}px</output></label><input type="range" id="font-size" min="17" max="27" step="1" bind:value={fontSize} />
  <div class="setting-row">Page theme<div class="segmented">{#each [['light', 'Light'], ['dark', 'Dark']] as [value, title]}<button class:active={theme === value} aria-pressed={theme === value} onclick={() => theme = value}>{title}</button>{/each}</div></div>
  <p class="setting-sample">In him was life, and the life was the light of men.</p>
</dialog>

<dialog bind:this={sourcesDialog} class="sources-dialog">
  <div class="dialog-heading"><h2>Sources & attribution</h2><button class="icon-button" aria-label="Close sources" onclick={() => sourcesDialog.close()}><Icon name="x" /></button></div>
  <div>
    <p>Scripture presents downloaded texts and scholarly datasets. Connections based on the same lemma are lexical matches; a shared word does not establish identical meaning or a theological conclusion.</p>
    <h3>English translation texts</h3><p>Public-domain editions are distributed through <a href="https://github.com/scrollmapper/bible_databases" target="_blank" rel="noreferrer">Scrollmapper’s Bible databases</a> (database tooling: MIT). The <a href="https://berean.bible/licensing.htm" target="_blank" rel="noreferrer">Berean Standard Bible is public domain</a>. The <a href="https://ebible.org/engwebp/copyright.htm" target="_blank" rel="noreferrer">World English Bible is public domain</a>, downloaded from <a href="https://github.com/TehShrike/world-english-bible" target="_blank" rel="noreferrer">TehShrike’s text repository</a>. KJV Crown rights apply in the United Kingdom. Book totals reflect each supplied edition, including any source appendices.</p>
    <p>KJV text comes from <a href="https://github.com/thiagobodruk/bible" target="_blank" rel="noreferrer">Thiago Bodruk’s Bible repository</a> (<a href={assetUrl('/licenses/KJV-repository-MIT.txt')}>repository license</a>). Source snapshots contain some empty verse entries, caused by edition omissions, numbering differences, or upstream extraction gaps. These are disclosed in the reader and download metadata. Entirely empty books and chapters are excluded.</p>
    <h3>Original-language texts & annotations</h3><p><a href="https://github.com/Clear-Bible/macula-hebrew/" target="_blank" rel="noreferrer">MACULA Hebrew Linguistic Datasets</a> and <a href="https://github.com/Clear-Bible/macula-greek/" target="_blank" rel="noreferrer">MACULA Greek Linguistic Datasets</a>, © 2022–2024 Biblica, Inc., CC BY 4.0. Original work of the Open Scriptures Hebrew Bible available at <a href="https://github.com/openscriptures/morphhb" target="_blank" rel="noreferrer">Open Scriptures</a>. Westminster Leningrad Codex text is public domain. Hebrew glosses: Cherith Glosses by Andi Wu, © 2022 Cherith Analytics, CC BY 4.0. Greek glosses: Berean Interlinear Bible, public domain.</p>
    <p>SBL Greek New Testament, © 2010 Society of Biblical Literature and Logos Bible Software, <a href={assetUrl('/licenses/SBLGNT.txt')}>CC BY 4.0</a>. Data has been converted into chapter JSON and lemma indexes; UBS semantic-domain fields are omitted. <a href={assetUrl('/licenses/macula-hebrew.md')}>Full Hebrew notices</a> · <a href={assetUrl('/licenses/macula-greek.md')}>Full Greek notices</a>.</p>
    <h3>References & verse numbering</h3><p><a href="https://www.openbible.info/labs/cross-references/" target="_blank" rel="noreferrer">OpenBible.info cross-references</a>, CC BY. Entries retain source vote rankings and ranges. Hebrew/English verse mapping comes from <a href="https://github.com/sillsdev/libpalaso" target="_blank" rel="noreferrer">SIL libpalaso</a> (<a href={assetUrl('/licenses/SIL.txt')}>license</a>). Whole-verse mappings are applied; some split-verse distinctions and textual variants are not represented. Native-numbered JPS, DRC, and CPDV editions remain readable, but automatic study alignment is disabled for them.</p>
    <h3>Encyclopedia, geography & research</h3><p>Wikipedia article excerpts are adapted and abridged under CC BY-SA 4.0. Each entry links to its source revision and contributor history. OpenBible.info geography is CC BY 4.0; candidate identifications and uncertainty are preserved. Online maps use OpenStreetMap, OpenTopoMap, and EOX Cloudless 2016 satellite imagery (CC BY 4.0), with provider credits displayed on the map. Satellite imagery is a dated mosaic, not a live view or ancient reconstruction. Elevation uses Mapterhorn terrain data.</p>
    <p>The <a href={assetUrl('/data/research/manifest.json')}>research source manifest</a> records authors, perspectives, dates, licenses, and coverage gaps. Historical texts do not represent every contemporary believer or school. The optional WebGPU assistant uses Qwen3. The Research desk distinguishes pretrained browser models from experimental custom training artifacts and reports their evaluation limits. Source search and inference run in this browser; model downloads use Hugging Face and GitHub.</p>
    <p>Download the <a href={assetUrl('/data/sources.json')} download>source URLs and SHA-256 checksums</a>. Each translation download includes its source and rights information. Code licensing does not replace the individual dataset licenses.</p>
  </div>
</dialog>
<div id="toast" class:visible={Boolean(toast)} role="status" aria-live="polite">{toast}</div>
