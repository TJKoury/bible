<script>
  import { onMount, tick, untrack } from 'svelte';
  import './research-layout.css';
  import Icon from './Icon.svelte';
  import { json, assetUrl } from './data.js';
  import { citationAudit, evidenceExcerpt, selectEvidence, normalizeCitations } from './retrieval.js';
  import { buildMessages, models } from './ai.js';
  import { LocalModel } from './model.js';
  import { inspectDevice, modelCompatibility } from './device.js';
  import training from '../../docs/training-result.json';
  let { questionRequest = null, context, active = true, onNavigate, onArticle } = $props();
  let question = $state('');
  let filters = $state([]);
  let history = $state([]);
  let selectedId = $state('');
  let deskTab = $state('research');
  let ready = $state(false);
  let indexStatus = $state('Preparing the local source index…');
  let indexError = $state('');
  let pendingCount = $state(0);
  let generatingId = $state('');
  let manifest = $state(null);
  let modelId = $state(models[0].id);
  let modelState = $state('idle');
  let modelProgress = $state(0);
  let modelMessage = $state('');
  let modelError = $state('');
  let device = $state(null);
  let capabilityError = $state('');
  let autoSearch = $state(false);
  let copied = $state(false);
  let showLibrary = $state(false);
  let dossier = $state(null);
  let desk;
  let chatViewport;
  let referencesViewport;
  let deskHeight = $state(650);
  let searchWorker;
  let engine;
  let sequence = 0, workerEpoch = 0, modelTicket = 0;
  let disposed = false, currentRun = null, contextKey = '', handledQuestion;
  const pending = new Map();
  const drafts = new Map();
  const traditions = ['Biblical texts', 'Christianity', 'Judaism', 'Islam', 'Encyclopedia'];
  const current = $derived(history.find(item => item.id === selectedId));
  const submitted = $derived(current?.question || '');
  const results = $derived(current?.results || []);
  const included = $derived(current?.included || []);
  const answer = $derived(current?.answer || '');
  const searching = $derived(current?.phase === 'searching');
  const answering = $derived(current?.phase === 'answering');
  const busy = $derived(pendingCount > 0 || !!generatingId);
  const evidence = $derived(evidenceFor(current));
  const visibleAnswer = $derived(normalizeCitations(answer.replace(/<think>[\s\S]*?<\/think>/g,'').replace(/<think>[\s\S]*$/g,'').trim()));
  const audit = $derived(citationAudit(visibleAnswer, evidence));
  const present = $derived([...new Set(results.map(r => r.tradition))]);
  const missing = $derived(['Christianity','Judaism','Islam'].filter(t => !present.includes(t)));
  const model = $derived(models.find(m => m.id === modelId));
  const answerModel = $derived(models.find(m => m.id === current?.answerModelId));
  const compatibility = $derived(modelCompatibility(model,device));
  const gpu = $derived(device?.supported && device?.f16);

  $effect(() => {
    const next = context.key;
    if (next === contextKey) return;
    untrack(() => {
      if (contextKey) drafts.set(contextKey, question);
      contextKey = next;
      const saved = history.findLast(item => item.context.key === next);
      selectedId = saved?.id || '';
      question = drafts.get(next) ?? `Compare interpretations of ${context.label} across relevant traditions.`;
      filters = saved ? [...saved.filters] : [];
      autoSearch = !saved;
    });
  });
  $effect(() => {
    if (questionRequest && questionRequest !== handledQuestion && questionRequest.contextKey === context.key) {
      handledQuestion = questionRequest;
      question = questionRequest.question || `Compare interpretations of ${context.label} across relevant traditions.`;
      deskTab = 'research'; autoSearch = true;
    }
  });
  $effect(() => { if (autoSearch && active && ready && !context.loading && !busy) untrack(() => { autoSearch = false; research(); }); });
  $effect(() => { if (active) { context.key; tick().then(measureDesk); } });
  onMount(() => {
    checkDevice(); startIndex();
    json('/data/research/dossiers.json').then(data => {
      if (!disposed) { const all = Array.isArray(data) ? data : data.dossiers || []; dossier = all.find(d => /romans/i.test(d.title || d.id)); }
    }).catch(() => {});
    const observer = new ResizeObserver(measureDesk);
    document.querySelectorAll('.topbar, .shared-context').forEach(element => observer.observe(element));
    window.addEventListener('resize', measureDesk);
    window.visualViewport?.addEventListener('resize', measureDesk);
    measureDesk();
    return () => {
      disposed = true; observer.disconnect();
      window.removeEventListener('resize', measureDesk);
      window.visualViewport?.removeEventListener('resize', measureDesk);
      searchWorker?.terminate(); engine?.dispose();
    };
  });
  function measureDesk() {
    if (!active || !desk || disposed) return;
    deskHeight = Math.max(0, (window.visualViewport?.height || window.innerHeight) - desk.getBoundingClientRect().top - 8);
  }
  function evidenceFor(item) {
    return (item?.results || []).filter(result => item.included.includes(result.id)).slice(0, 8)
      .map((result, index) => ({ ...result, citation: `[S${index + 1}]`, excerpt: evidenceExcerpt(result.text, item.question, 2200) }));
  }
  async function checkDevice() { capabilityError = ''; try { device = await inspectDevice(); } catch { capabilityError = 'Device checks could not complete.'; } }
  function startIndex() {
    const epoch = ++workerEpoch;
    ready = false; indexError = ''; indexStatus = 'Preparing the local source index…';
    searchWorker?.terminate();
    for (const id of pending.values()) {
      const item = history.find(entry => entry.id === id);
      if (item) { item.phase = 'error'; item.error = 'Source search was interrupted. Submit the question again to retry.'; }
    }
    pending.clear(); pendingCount = 0;
    searchWorker = new Worker(new URL('./research.worker.js', import.meta.url), { type: 'module' });
    searchWorker.onmessage = ({ data }) => {
      if (disposed || epoch !== workerEpoch) return;
      if (data.type === 'progress') indexStatus = data.text;
      if (data.type === 'ready') { ready = true; manifest = data.manifest; indexStatus = `${data.count.toLocaleString()} searchable passages`; }
      if (data.type === 'results' || (data.type === 'error' && data.request)) {
        const id = pending.get(data.request);
        if (!id) return;
        pending.delete(data.request); pendingCount = pending.size;
        const item = history.find(entry => entry.id === id);
        if (!item) return;
        if (data.type === 'error') { item.error = data.message; item.phase = 'error'; return; }
        item.results = data.results; item.included = selectEvidence(data.results); item.phase = 'ready';
        if (item.autoDraft && modelState === 'ready' && !generatingId && item.included.length) generate(id);
      } else if (data.type === 'error') indexError = data.message;
    };
    searchWorker.onerror = () => {
      if (disposed || epoch !== workerEpoch) return;
      ready = false; indexError = 'The source index could not start. Retry loading the research library.';
      for (const id of pending.values()) {
        const item = history.find(entry => entry.id === id);
        if (item) { item.phase = 'error'; item.error = indexError; }
      }
      pending.clear(); pendingCount = 0;
    };
    searchWorker.postMessage({ type: 'init' });
  }
  function research(event) {
    event?.preventDefault();
    if (!question.trim() || !ready || busy || context.loading) return;
    const id = `question-${++sequence}`;
    const snapshot = JSON.parse(JSON.stringify(context));
    const prompt = question.trim();
    history = [...history, { id, question: prompt, context: snapshot, filters: [...filters], results: [], included: [], answer: '', answerModelId: '', phase: 'searching', error: '', autoDraft: modelState === 'ready' || modelState === 'loading' }];
    selectedId = id; deskTab = 'research'; copied = false; question = ''; autoSearch = false;
    pending.set(sequence, id); pendingCount = pending.size;
    searchWorker.postMessage({ type: 'search', request: sequence, question: prompt, traditions: [...filters], context: snapshot });
    tick().then(() => { if (selectedId === id) { chatViewport?.scrollTo(0, 0); referencesViewport?.scrollTo(0, 0); } });
  }
  function selectQuestion(id) {
    selectedId = id; copied = false; deskTab = 'research'; autoSearch = false;
    const item = history.find(entry => entry.id === id);
    if (item) filters = [...item.filters];
    tick().then(() => { chatViewport?.scrollTo(0, 0); referencesViewport?.scrollTo(0, 0); });
  }
  function toggleFilter(tradition) { filters = filters.includes(tradition) ? filters.filter(t => t !== tradition) : [...filters, tradition]; }
  function toggleEvidence(id) {
    if (!current || answering) return;
    current.answer = ''; current.answerModelId = ''; current.error = ''; current.phase = 'ready';
    if (included.includes(id)) current.included = included.filter(value => value !== id);
    else if (included.length < 8) current.included = [...included, id];
  }
  async function loadModel() {
    if (!compatibility.allowed) return;
    // Keep the intent on the question, regardless of which operation finishes first.
    if (current && !current.answer && ['searching', 'ready'].includes(current.phase)) current.autoDraft = true;
    const ticket = ++modelTicket;
    modelState = 'loading'; modelProgress = 0; modelError = '';
    modelMessage = 'Checking this device’s WebGPU support…';
    try {
      const adapter = await navigator.gpu?.requestAdapter();
      if (!adapter) throw new Error('WebGPU is unavailable on this device. Source search works without a model.');
      if (!adapter.features.has('shader-f16')) throw new Error('This model requires WebGPU shader-f16 support. Try a current desktop Chrome or Edge with GPU acceleration enabled.');
      if (ticket !== modelTicket || disposed) return;
      engine?.dispose();
      engine = new LocalModel(progress => {
        if (ticket !== modelTicket || disposed) return;
        modelProgress = Math.max(0, Math.min(1, progress.progress || 0)); modelMessage = progress.text;
      });
      await engine.load(modelId);
      if (ticket !== modelTicket || disposed) return;
      modelState = 'ready'; modelMessage = 'Ready · answers run on this device';
      const waiting = history.findLast(item => item.autoDraft && item.phase === 'ready' && !item.answer && item.included.length);
      if (waiting && !busy) generate(waiting.id);
    } catch (e) {
      if (ticket === modelTicket && !disposed) { modelState = 'idle'; modelError = e.message || 'The model could not load. Check available GPU memory and connection.'; engine?.dispose(); engine = null; }
    }
  }
  function unloadModel() {
    ++modelTicket;
    if (currentRun) {
      currentRun.stopped = true;
      const item = history.find(entry => entry.id === currentRun.id);
      if (item) item.phase = 'stopped';
    }
    currentRun = null; generatingId = ''; engine?.dispose(); engine = null;
    modelState = 'idle'; modelMessage = ''; modelProgress = 0;
  }
  async function clearModel() {
    unloadModel(); const cleaner = new LocalModel();
    try { await cleaner.clear(modelId); modelMessage = 'Selected model removed from this browser’s cache.'; }
    catch { modelError = 'The cache could not be cleared. You can remove this site’s storage in browser settings.'; }
    finally { cleaner.dispose(); }
  }
  async function generate(id) {
    const item = history.find(entry => entry.id === id);
    const packet = evidenceFor(item);
    if (!engine || modelState !== 'ready' || !packet.length || generatingId || !item) return;
    const run = { id, ticket: modelTicket, stopped: false };
    currentRun = run; generatingId = id;
    item.phase = 'answering'; item.answer = ''; item.error = ''; item.answerModelId = modelId;
    try {
      await engine.generate(buildMessages(`${item.question}\nCurrent reading context: ${item.context.label} (${item.context.edition}).`, packet), delta => {
        if (currentRun === run && run.ticket === modelTicket && !disposed) item.answer += delta;
      });
    } catch (e) {
      if (currentRun === run && run.ticket === modelTicket && !disposed) { item.error = `Generation stopped: ${e.message || 'the device ran out of resources'}`; run.stopped = true; }
    } finally {
      if (currentRun === run && !disposed) { item.phase = run.stopped ? 'stopped' : 'answered'; currentRun = null; generatingId = ''; }
    }
  }
  function stop() { if (currentRun) currentRun.stopped = true; engine?.interrupt().catch(() => {}); }
  function focusReference(citation) {
    if (!referencesViewport || !/^\[S\d+\]$/.test(citation)) return;
    const target = referencesViewport.querySelector(`[data-citation="${citation}"]`);
    if (!target) return;
    referencesViewport.scrollTo({ top: referencesViewport.scrollTop + target.getBoundingClientRect().top - referencesViewport.getBoundingClientRect().top - 12, behavior: 'smooth' });
    target.focus({ preventScroll: true });
  }
  function tabKey(event) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault(); deskTab = event.key === 'Home' ? 'research' : event.key === 'End' ? 'advanced' : deskTab === 'research' ? 'advanced' : 'research';
    tick().then(() => desk?.querySelector(`#research-tab-${deskTab}`)?.focus());
  }
  function exportText() {
    return `# ${submitted}\n\nReading context: ${current?.context.label || ''} (${current?.context.edition || ''})\n\n${visibleAnswer || 'Source research packet; no AI synthesis generated.'}\n\n## Evidence\n\n${evidence.map(e => `${e.citation} ${e.title}\n${e.author || ''} · ${e.tradition} · ${e.perspective || ''}\n${e.locator || ''}\n${e.excerpt}\nSource: ${e.sourceUrl || ''}\nLicense: ${e.license || ''}`).join('\n\n')}\n\nCitation identifiers ${audit.unknown.length ? 'include unresolved references' : 'checked against the evidence packet'}. Claim entailment and attribution are not independently verified. Corpus is selective, not exhaustive. Browser model: ${current?.answerModelId || 'none'}; ${answerModel?.custom ? 'experimental custom historical-text adaptation' : 'pretrained model or source retrieval only'}.\n`;
  }
  async function copy() {
    const id = selectedId;
    try { await navigator.clipboard.writeText(exportText()); if (id === selectedId) copied = true; setTimeout(() => copied = false, 2500); }
    catch { if (current?.id === id) current.error = 'Copy was unavailable. Use Download notes instead.'; }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([exportText()], { type: 'text/markdown;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = 'scripture-research.md'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
</script>

<section class="research-desk" bind:this={desk} style:height={`${deskHeight}px`} aria-label="Research desk">
  <header class="desk-heading"><h1>Research desk</h1><div class="desk-tabs" role="tablist" aria-label="Research workspace">{#each ['research', 'advanced'] as tab}<button id={`research-tab-${tab}`} role="tab" aria-selected={deskTab === tab} aria-controls={`research-panel-${tab}`} tabindex={deskTab === tab ? 0 : -1} class:active={deskTab === tab} onclick={() => deskTab = tab} onkeydown={tabKey}>{tab === 'research' ? 'Research' : 'Advanced'}</button>{/each}</div></header>
  <div class="desk-workspace" id="research-panel-research" role="tabpanel" aria-labelledby="research-tab-research" hidden={deskTab !== 'research'}>
    <div class="desk-upper">
      <aside class="question-timeline" aria-label="Question history">
        <h2>Questions <span>{history.length}</span></h2>
        <nav class="timeline-scroll" aria-label="Previous research questions">
          {#if !history.length}<p class="timeline-empty">Your questions will appear here.</p>{/if}
          <ol>{#each history as item, index (item.id)}<li><button class:active={selectedId === item.id} aria-current={selectedId === item.id ? 'true' : undefined} aria-label={`Question ${index + 1}: ${item.question}. ${item.context.label}. ${item.phase === 'searching' ? 'Searching' : item.phase === 'answering' ? 'Writing' : 'Saved in this session'}`} title={item.question} onclick={() => selectQuestion(item.id)}><span class="timeline-number">{index + 1}</span><span class="timeline-copy"><strong>{item.question}</strong><small>{item.context.label}{#if item.phase === 'searching' || item.phase === 'answering'} · {item.phase === 'searching' ? 'Searching' : 'Writing'}{/if}</small></span></button></li>{/each}</ol>
        </nav>
        <p class="timeline-foot">This session</p>
      </aside>
      <section class="desk-conversation" aria-label="Research conversation">
        <!-- svelte-ignore a11y_no_noninteractive_tabindex (The independent scroll region needs a keyboard focus target.) -->
        <div class="conversation-scroll" bind:this={chatViewport} role="region" aria-label="Question and answer" tabindex="0" aria-busy={searching || answering}>
          {#if !current}<div class="conversation-empty"><Icon name="spark" size={25} /><h2>Research</h2><p>Explore {context.label} through biblical texts, historical works, and sources from different traditions.</p></div>
          {:else}
            <div class="conversation-question"><span class="conversation-speaker">You <small>{current.context.label} · {current.context.edition}</small></span><h2>{submitted}</h2></div>
            <div class="conversation-response">
              <div class="response-heading"><span class="conversation-speaker">Research</span><div class="response-actions">{#if answering}<button class="subtle-button" onclick={stop}>Stop</button>{/if}<button class="icon-button" aria-label={copied ? 'Notes copied' : 'Copy research notes'} title={copied ? 'Copied' : 'Copy notes'} onclick={copy} disabled={!results.length}><Icon name={copied ? 'check' : 'copy'} size={16} /></button><button class="icon-button" aria-label="Download research notes" title="Download notes" onclick={download} disabled={!results.length}><Icon name="download" size={16} /></button></div></div>
              {#if searching}<p class="conversation-status" role="status">Finding relevant sources…</p>
              {:else if current.error}<p class="error-note" role="alert">{current.error}</p>{/if}
              {#if visibleAnswer}
                <div class="research-answer">{#each visibleAnswer.split('\n').filter(Boolean) as line}{#if /^#{1,4}\s/.test(line)}<h3>{line.replace(/^#{1,4}\s/,'').replace(/\*\*/g,'')}</h3>{:else}<p>{#each line.replace(/\*\*/g,'').split(/(\[S\d+\])/g) as part}{#if /^\[S\d+\]$/.test(part)}<button class="citation-link" class:invalid-citation={audit.unknown.includes(part)} onclick={() => focusReference(part)} aria-label={`Show source ${part}`}>{part}</button>{:else}{part}{/if}{/each}</p>{/if}{/each}</div>
              {:else if answering}<p class="conversation-status" role="status">Drafting a comparison on this device…</p>
              {:else if !searching && results.length}
                <p>Found {results.length} relevant source passages. The references below include {evidence.length} selected excerpts for comparison.</p>
                {#if modelState !== 'ready'}<p class="conversation-hint">Read the evidence now, or load a local model in <button onclick={() => deskTab = 'advanced'}>Advanced</button> for a cited draft.</p>
                {:else if current.phase === 'answered' || current.phase === 'stopped'}<p class="conversation-hint">{current.phase === 'stopped' ? 'The draft was stopped.' : 'The model returned no final answer.'} Research a narrower question to try again.</p>
                {:else}<p class="conversation-hint">The selected evidence is ready. <button disabled={busy || !evidence.length} onclick={() => generate(current.id)}>Draft from these references</button>.</p>{/if}
              {:else if !searching && !current.error}<p>No relevant passages were found. Try a narrower name, passage, or theological term.</p>{/if}
              {#if answer || answering}<p class="draft-caption">{answering ? 'Writing locally…' : `${answerModel?.title || 'Local model'} · ${current.phase === 'stopped' ? 'stopped draft' : 'AI draft'}`} · Verify against the sources.</p>{/if}
              {#if visibleAnswer}<details class="attribution-audit"><summary>Attribution check</summary><p>{audit.unknown.length ? `Unresolved citations: ${audit.unknown.join(', ')}.` : audit.hasCitations ? `${audit.cited.length} citation identifiers match the evidence packet.` : 'The draft has no source citations.'} Matching identifiers do not prove the claims are supported.</p><ul><li>Does the author endorse the view or describe someone else’s?</li><li>Does the excerpt support the whole claim?</li><li>Are contested conclusions and missing traditions acknowledged?</li></ul></details>{/if}
            </div>
          {/if}
        </div>
        <form class="desk-composer" onsubmit={research}>
          <label for="research-question">Ask about {context.label}</label>
          <div class="composer-row"><textarea id="research-question" bind:value={question} placeholder="Ask a question or follow an idea…" rows="2" maxlength="1200" onkeydown={event => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') research(event); }}></textarea><button class="primary-button" type="submit" disabled={!ready || !question.trim() || busy || context.loading}>Research<Icon name="arrow-right" size={16} /></button></div>
          <p class="composer-status" role="status">{!ready ? indexStatus : pendingCount ? 'Finding sources…' : generatingId ? 'Writing a comparison…' : modelState === 'ready' ? 'Local model ready' : 'Source research'}</p>
          {#if indexError}<p class="error-note">{indexError} Open Advanced to retry.</p>{/if}
        </form>
      </section>
    </div>
    <section class="desk-references" aria-label="Research references">
      <header class="references-heading"><h2>References <span>{results.length}</span></h2><div class="reference-options"><span class="reference-count">{evidence.length} / 8 selected</span><details class="source-options"><summary>Source traditions</summary><div class="source-options-menu"><p>Applies to the next question. No tradition is preferred.</p><div class="tradition-filters" role="group" aria-label="Research source traditions"><button class:active={!filters.length} aria-pressed={!filters.length} onclick={() => filters = []}>All sources</button>{#each traditions as tradition}<button class:active={filters.includes(tradition)} aria-pressed={filters.includes(tradition)} onclick={() => toggleFilter(tradition)}>{tradition}</button>{/each}</div></div></details></div></header>
      <!-- svelte-ignore a11y_no_noninteractive_tabindex (The independent scroll region needs a keyboard focus target.) -->
      <div class="references-scroll" bind:this={referencesViewport} role="region" aria-label="Source passages" tabindex="0" aria-busy={searching}>
        {#if results.length}
          <p class="references-coverage">{present.join(' · ')}{#if missing.length} · No retrieved evidence from {missing.join(', ')}.{/if} Coverage gaps do not mean a tradition has no view.</p>
          <div class="evidence-list">{#each results as result (result.id)}{@const selectedEvidence = evidence.find(e => e.id === result.id)}<article class="evidence-card" data-citation={selectedEvidence?.citation} tabindex="-1"><div class="evidence-heading"><label><input type="checkbox" aria-label={`Include ${result.title} in the evidence packet`} checked={included.includes(result.id)} disabled={answering || (!included.includes(result.id) && included.length >= 8)} onchange={() => toggleEvidence(result.id)} /><span>{selectedEvidence?.citation || 'Add'}</span></label><span class="tradition-badge">{result.tradition}</span>{#if result.editorial}<span class="outline-badge">Editorial summary</span>{/if}</div><h3>{result.title}</h3><p class="evidence-meta">{result.author} · {result.perspective}{#if result.publicationDate} · {result.publicationDate}{/if}<br>{result.locator}</p><blockquote>{evidenceExcerpt(result.text,submitted,850)}</blockquote><div class="inline-actions">{#if result.ref}<button class="subtle-button" onclick={() => onNavigate(result.ref,result.edition || 'BSB')}>Read passage<Icon name="arrow-right" /></button>{:else if result.articleId}<button class="subtle-button" onclick={() => onArticle(result.articleId)}>Read study article<Icon name="arrow-right" /></button>{/if}{#if result.sourceUrl}<a class="subtle-button" href={result.sourceUrl} target="_blank" rel="noreferrer">Original source ↗</a>{/if}<details><summary>Full indexed passage</summary><p class="full-evidence">{result.text}</p><p class="source-caption">{result.license}</p></details></div></article>{/each}</div>
        {:else}<div class="references-empty"><Icon name="library" /><p>{searching ? 'Gathering passages and source details…' : 'Sources for the selected question will appear here.'}</p></div>{/if}
      {#if dossier && /romans\s*9/i.test(submitted)}
        <section class="dossier-note"><p class="eyebrow">SOURCE-LINKED RESEARCH NOTE</p><h2>{dossier.title}</h2><p>{dossier.context}</p>
          <h3>Interpretations compared</h3>
          {#each dossier.positions || [] as position}<div class="dossier-position"><span class="tradition-badge">{position.perspective}</span><h3>{position.author} · {position.label}</h3><p>{position.summary}</p>{#each position.evidence || [] as item}{@const source = dossier.sources.find(s => s.id === item.sourceId)}<div class="dossier-evidence"><p>{item.claim}</p><small>{item.role} · {item.locator}</small>{#if source}<a href={source.url} target="_blank" rel="noreferrer">{source.author} ({source.date}) · original source ↗</a>{/if}</div>{/each}</div>{/each}
          <h3>Where the disagreement remains</h3><p>{dossier.conclusion}</p>
          <h3>Attribution corrections</h3>
          {#each dossier.attributionAudit || [] as item}<div class="dossier-evidence"><strong>{item.claim}</strong><p>{item.status} · {item.reason}</p></div>{/each}
          <p class="source-caption">This note compares named scholarly positions. It does not settle the question or represent every Christian tradition. Romans is not a canonical scripture of Judaism or Islam; comparison must not attribute Pauline doctrines to those traditions.</p>
        </section>
      {/if}

      </div>
    </section>
  </div>
  <div class="desk-advanced" id="research-panel-advanced" role="tabpanel" aria-labelledby="research-tab-advanced" hidden={deskTab !== 'advanced'}>
    <div class="advanced-intro">{#if indexError}<p class="error-note">{indexError} <button onclick={startIndex}>Retry index</button></p>{/if}<h2>Models & library</h2><p>Optional local answers, source downloads, and the custom training pipeline.</p><p class="source-caption">{indexStatus}</p></div>
    <div class="advanced-grid">
      <div class="model-card"><h2>Local model</h2><p>Source retrieval and optional WebGPU answers run in this browser.</p>
        {#if !device}<p class="source-caption" role="status">Checking device capabilities before showing model downloads…</p>{/if}
        {#if capabilityError}<p class="error-note">{capabilityError}</p><button class="subtle-button" onclick={checkDevice}>Retry device check</button>{/if}
        {#if device}
          <details class="device-details"><summary>Device capabilities</summary><p>{device.localHost?.cpu || device.adapter}<br>{device.logicalCores || 'Unknown'} logical CPU cores{#if device.localHost}<br>{Math.round(device.localHost.totalMemory / 1024**3)} GB host memory{:else if device.reportedMemoryGB}<br>{device.reportedMemoryGB} GB browser-reported memory (privacy capped){/if}<br>WebGPU: {device.supported ? 'available' : 'unavailable'} · float16: {device.f16 ? 'available' : 'unavailable'}{#if device.storageAvailable !== null}<br>{(device.storageAvailable / 1024**3).toFixed(1)} GB browser cache quota available{/if}</p><p>Browsers do not expose free GPU memory. Download size and runtime memory are different; loading is the final compatibility check.</p><button class="text-button" disabled={modelState!=='idle'} onclick={checkDevice}>Refresh capabilities</button></details>
          {#if !gpu}<p class="error-note">This browser does not provide the WebGPU features these models need. Source search and exports remain available.</p>
          {:else}
            <label for="model-choice">Browser model</label><select id="model-choice" bind:value={modelId} disabled={modelState !== 'idle'}>{#each models as item}{@const fit=modelCompatibility(item,device)}<option value={item.id} disabled={!fit.allowed}>{item.title}{fit.allowed?'':' · exceeds reported capacity'}</option>{/each}</select><p class="source-caption">{model?.detail}. Estimates vary by browser and context length.</p><p class="source-caption">{compatibility.reason}.</p>
            {#if modelState === 'idle'}<button class="primary-button" onclick={loadModel} disabled={!compatibility.allowed}><Icon name="download" />Load local model</button>
            {:else if modelState === 'loading'}<progress value={modelProgress} max="1" aria-label="Model download progress"></progress><p class="source-caption" role="status">{modelMessage}</p><button class="subtle-button" onclick={unloadModel}>Cancel loading</button>
            {:else}<span class="model-ready"><span class="source-dot"></span>Running locally · WebGPU</span><button class="subtle-button" onclick={unloadModel}>Unload from GPU</button>{/if}
          {/if}
        {/if}
        {#if modelError}<p class="error-note" role="alert">{modelError}</p>{/if}
        {#if modelState === 'idle' && modelMessage}<p class="source-caption" role="status">{modelMessage}</p>{/if}
        <details><summary>Download & privacy details</summary><p>Loading downloads weights from this site or Hugging Face and a runtime from GitHub. They may be cached in this browser. Questions and excerpts are not sent to a model API. Online encyclopedia links and map tiles use their respective websites.</p><p>Qwen3 is distributed under Apache 2.0. Scripture 0.6B uses experimental custom training on historical texts. Neither the base nor the custom model is validated as a theological authority.</p><a href="https://huggingface.co/Qwen/Qwen3-0.6B" target="_blank" rel="noreferrer">Model card & license ↗</a><button class="text-button" disabled={modelState === 'loading' || answering} onclick={clearModel}>Remove selected model from browser cache</button></details>
      </div>
      <div class="corpus-card"><p class="eyebrow">THE RESEARCH LIBRARY</p><h3>{manifest?.sources?.length || '…'} works</h3><p>Historical texts with author, translator, school, and reuse information. Selected passages from the Bible and Wikipedia add context.</p><button class="subtle-button" onclick={() => showLibrary = !showLibrary}>{showLibrary ? 'Hide source inventory' : 'Inspect source inventory'}<Icon name="chevron-right" /></button>{#if showLibrary}<div class="source-inventory">{#each manifest?.sources || [] as source}<div><a href={source.sourceUrl} target="_blank" rel="noreferrer">{source.title} ↗</a><p>{source.author} · {source.publicationDate}<br>{source.tradition} · {source.perspective}<br>{source.license}</p></div>{/each}</div>{/if}<p class="source-caption">Selective historical coverage. Contemporary voices and internal diversity remain incomplete. Public-domain age is not a quality ranking.</p><a href={assetUrl('/data/research/manifest.json')} download class="subtle-button"><Icon name="download" />Source manifest</a></div>
      <div class="corpus-card"><h3>Custom model training</h3><p>Experimental Qwen3 0.6B: {training.training.iterations} training steps on {training.data.trainPassages.toLocaleString()} passages, with equal passage counts from Christianity, Judaism, and Islam.</p><p class="source-caption">Select Scripture 0.6B above to run the custom model on WebGPU. The separate MLX download supports the local training tools.</p><details class="training-results"><summary>Evaluation results</summary><table><thead><tr><th>Variant</th><th>Perplexity</th></tr></thead><tbody><tr><td>Base</td><td>{training.heldoutMetrics.base.perplexity}</td></tr><tr><td>Trained adapter</td><td>{training.heldoutMetrics.adapter.perplexity}</td></tr><tr><td>MLX 4-bit export</td><td>{training.heldoutMetrics.requantizedMlx4bit.perplexity}</td></tr><tr><td>Browser MLC export</td><td>Not scored</td></tr></tbody></table><p>Lower is better text prediction, not proof of theological accuracy. Quantization lost most of the adapter's gain. Answer probes still contain attribution and summary errors. Browser loading and generation were verified, but these loss scores do not evaluate browser answers. Wikipedia was not included in this experiment.</p></details><a class="subtle-button" href="https://github.com/TJKoury/bible/blob/main/docs/training-small-model.md" target="_blank" rel="noreferrer">Training report & pipeline ↗</a><a class="subtle-button" href="https://github.com/TJKoury/bible/releases/download/scripture-model-v2/scripture-qwen3-0.6b-v2-mlx4bit.tar.gz"><Icon name="download" />Download trained MLX model</a><a href={assetUrl('/data/research/chunks.json')} download class="subtle-button"><Icon name="download" />Download text corpus</a></div>

    </div>
  </div>
</section>
