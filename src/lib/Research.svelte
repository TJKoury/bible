<script>
  import { onMount, untrack } from 'svelte';
  import Icon from './Icon.svelte';
  import { json, assetUrl } from './data.js';
  import { citationAudit, evidenceExcerpt, selectEvidence, normalizeCitations } from './retrieval.js';
  import { buildMessages, models } from './ai.js';
  import { LocalModel } from './model.js';
  import { inspectDevice, modelCompatibility } from './device.js';
  import training from '../../docs/training-result.json';
  let { questionRequest = null, context, active = true, onNavigate, onArticle } = $props();
  let question = $state('');
  let submitted = $state('');
  let status = $state('Preparing the local source index…');
  let ready = $state(false);
  let searching = $state(false);
  let error = $state('');
  let manifest = $state(null);
  let documentCount = $state(0);
  let results = $state([]);
  let included = $state([]);
  let filters = $state([]);
  let answer = $state('');
  let answering = $state(false);
  let modelId = $state(models[0].id);
  let modelState = $state('idle');
  let modelProgress = $state(0);
  let modelMessage = $state('');
  let modelError = $state('');
  let device = $state(null);
  let capabilityError = $state('');
  let gpu = $derived(device?.supported && device?.f16);
  let autoSearch = $state(false);
  let copied = $state(false);
  let showLibrary = $state(false);
  let dossier = $state(null);
  let searchWorker;
  let engine;
  let request = 0;
  let modelTicket = 0;
  let disposed = false;
  let generation = 0, contextKey = '', handledQuestion;
  const sessions = new Map();
  const traditions = ['Biblical texts', 'Christianity', 'Judaism', 'Islam', 'Encyclopedia'];
  const evidence = $derived(results.filter(r => included.includes(r.id)).slice(0, 8).map((r, i) => ({...r,citation:`[S${i+1}]`,excerpt:evidenceExcerpt(r.text, submitted, 2200)})));
  const visibleAnswer = $derived(normalizeCitations(answer.replace(/<think>[\s\S]*?<\/think>/g,'').replace(/<think>[\s\S]*$/g,'').trim()));
  const audit = $derived(citationAudit(visibleAnswer, evidence));
  const present = $derived([...new Set(results.map(r => r.tradition))]);
  const missing = $derived(['Christianity','Judaism','Islam'].filter(t => !present.includes(t)));
  const model = $derived(models.find(m => m.id === modelId));
  const compatibility = $derived(modelCompatibility(model,device));
  $effect(() => {
    const next = context.key;
    if(next===contextKey)return;
    untrack(() => {
      if(contextKey)sessions.set(contextKey,{question,submitted,results,included,answer,filters,status});
      generation++;engine?.interrupt().catch(()=>{});answering=false;searching=false;request++;
      contextKey=next;
      const saved=sessions.get(next);
      question=saved?.question || `Compare interpretations of ${context.label} across relevant traditions.`;
      submitted=saved?.submitted || '';results=saved?.results || [];included=saved?.included || [];
      answer=saved?.answer || '';filters=saved?.filters || [];status=saved?.status || 'Current passage selected';
      autoSearch=!saved?.submitted || !saved?.results.length;
    });
  });
  $effect(() => {
    if (questionRequest && questionRequest!==handledQuestion && questionRequest.contextKey===context.key) { handledQuestion=questionRequest;question = questionRequest.question || `Compare interpretations of ${context.label} across relevant traditions.`;autoSearch=true; }
  });
  $effect(() => { if(autoSearch && active && ready && !context.loading)untrack(()=>{autoSearch=false;search();}); });
  onMount(() => {
    checkDevice();
    startIndex();
    json('/data/research/dossiers.json').then(data => { const all = Array.isArray(data) ? data : data.dossiers || []; dossier = all.find(d => /romans/i.test(d.title || d.id)); }).catch(() => {});
    return () => { disposed = true; searchWorker?.terminate(); engine?.dispose(); };
  });
  async function checkDevice() { capabilityError='';try{device=await inspectDevice();}catch{capabilityError='Device checks could not complete.';} }
  function startIndex() {
    ready = false; error = ''; status = 'Preparing the local source index…';
    searchWorker?.terminate();
    searchWorker = new Worker(new URL('./research.worker.js', import.meta.url), {type:'module'});
    searchWorker.onmessage = ({data}) => {
      if (data.type === 'progress') status = data.text;
      if (data.type === 'ready') { ready = true; manifest = data.manifest; documentCount = data.count; status = `${data.count.toLocaleString()} searchable passages`; }
      if (data.type === 'results' && data.request === request) {
        results = data.results; included = selectEvidence(results); searching = false;
        status = `${results.length} source passages found`;
      }
      if (data.type === 'error' && (!data.request || data.request === request)) { error = data.message; searching = false; }
    };
    searchWorker.onerror = () => { error = 'The source index could not start. Retry loading the research library.'; searching = false; };
    searchWorker.postMessage({type:'init'});
  }
  function search(event) {
    event?.preventDefault();
    if (!question.trim() || !ready || answering) return;
    submitted = question.trim(); searching = true; results = []; answer = ''; error = '';
    searchWorker.postMessage({type:'search',request:++request,question:submitted,traditions:[...filters],context:JSON.parse(JSON.stringify(context))});
  }
  function toggleFilter(tradition) {
    if (answering) return;
    filters = filters.includes(tradition) ? filters.filter(t => t !== tradition) : [...filters,tradition];
  }
  function toggleEvidence(id) {
    answer = '';
    if (included.includes(id)) included = included.filter(value => value !== id);
    else if (included.length < 8) included = [...included, id];
  }
  async function loadModel() {
    if(!compatibility.allowed)return;
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
    } catch (e) {
      if (ticket === modelTicket && !disposed) { modelState = 'idle'; modelError = e.message || 'The model could not load. Check available GPU memory and connection.'; engine?.dispose(); engine = null; }
    }
  }
  function unloadModel() {
    ++modelTicket; engine?.dispose(); engine = null;
    answering = false; modelState = 'idle'; modelMessage = ''; modelProgress = 0;
  }
  async function clearModel() {
    unloadModel();
    const cleaner = new LocalModel();
    try { await cleaner.clear(modelId); modelMessage = 'Selected model removed from this browser’s cache.'; }
    catch { modelError = 'The cache could not be cleared. You can remove this site’s storage in browser settings.'; }
    finally { cleaner.dispose(); }
  }
  async function generate() {
    if (!engine || !evidence.length || answering) return;
    const ticket = modelTicket;
    const currentGeneration = ++generation;
    answering = true; answer = ''; modelError = '';
    try {
      await engine.generate(buildMessages(`${submitted}\nCurrent reading context: ${context.label} (${context.edition}).`,evidence), delta => {
        if (ticket === modelTicket && currentGeneration===generation && !disposed) answer += delta;
      });
    } catch (e) { if (ticket === modelTicket && currentGeneration===generation) modelError = `Generation stopped: ${e.message || 'the device ran out of resources'}`; }
    finally { if (ticket === modelTicket && currentGeneration===generation && !disposed) answering = false; }
  }
  function stop() { engine?.interrupt().catch(() => {}); }
  function exportText() {
    return `# ${submitted}\n\n${visibleAnswer || 'Source research packet; no AI synthesis generated.'}\n\n## Evidence\n\n${evidence.map(e => `${e.citation} ${e.title}\n${e.author || ''} · ${e.tradition} · ${e.perspective || ''}\n${e.locator || ''}\n${e.excerpt}\nSource: ${e.sourceUrl || ''}\nLicense: ${e.license || ''}`).join('\n\n')}\n\nCitation identifiers ${audit.unknown.length ? 'include unresolved references' : 'checked against the evidence packet'}. Claim entailment and attribution are not independently verified. Corpus is selective, not exhaustive. Browser model: ${modelId}; ${model?.custom ? 'experimental custom historical-text adaptation' : 'pretrained model'}. \n`;
  }
  async function copy() { try { await navigator.clipboard.writeText(exportText()); copied = true; setTimeout(() => copied = false, 2500); } catch { error = 'Copy was unavailable. Use Download notes instead.'; } }
  function download() {
    const url = URL.createObjectURL(new Blob([exportText()], {type:'text/markdown;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = 'scripture-research.md'; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
  }
</script>

<section class="explore-view research-view">
  <div class="explore-heading"><h1>Research desk</h1></div>
  <div class="research-layout">
    <div class="research-main">
      <form class="question-box" onsubmit={search}>
        <label for="research-question">What would you like to understand?</label>
        <textarea id="research-question" bind:value={question} placeholder={`Ask about ${context.label}`} rows="3" maxlength="1200"></textarea>
        <div class="question-footer"><span><Icon name="library" />Search sources first</span><button class="primary-button" disabled={!ready || !question.trim() || searching || answering} type="submit">{searching ? 'Searching…' : 'Find evidence'}<Icon name="arrow-right" /></button></div>
      </form>
      <div class="tradition-filters" role="group" aria-label="Research source traditions"><button class:active={!filters.length} aria-pressed={!filters.length} onclick={() => filters = []} disabled={answering}>All sources</button>{#each traditions as tradition}<button class:active={filters.includes(tradition)} aria-pressed={filters.includes(tradition)} onclick={() => toggleFilter(tradition)} disabled={answering}>{tradition}</button>{/each}</div>
      <p class="source-caption">No preferred tradition. Relevance and source diversity guide retrieval; results reflect the downloaded collection, not a vote on what is true.</p>
      {#if error}<p class="error-note">{error} {#if !ready}<button onclick={startIndex}>Retry index</button>{/if}</p>{/if}
      <p class="research-status" role="status">{status}</p>
      {#if !submitted}
        <div class="question-suggestions"><p class="section-label">START WITH A QUESTION</p>{#each [`Compare interpretations of ${context.label} across relevant traditions.`, `What historical context helps explain ${context.label}?`, `Which places and people are mentioned in ${context.label}?`] as suggested}<button onclick={() => { question = suggested; search(); }} disabled={!ready}>{suggested}<Icon name="arrow-up-right" /></button>{/each}</div>
      {:else if !searching}
        <div class="research-result-heading"><div><p class="eyebrow">YOUR RESEARCH QUESTION</p><h2>{submitted}</h2></div><div class="inline-actions"><button class="subtle-button" onclick={copy} disabled={!evidence.length}><Icon name="copy" />{copied ? 'Copied' : 'Copy'}</button><button class="subtle-button" onclick={download} disabled={!evidence.length}><Icon name="download" />Notes</button></div></div>
        {#if !results.length}<p class="empty-note">No relevant source passages were found. Try a narrower name, passage, or theological term. The app will not fill the gap with an unsupported answer.</p>
        {:else}
          <div class="coverage-note"><Icon name="library" /><div><strong>Coverage in this search</strong><p>{present.join(' · ')}{#if missing.length}<br>No retrieved evidence from: {missing.join(', ')}.{/if} Missing perspectives are a research gap, not evidence that those traditions have no view.</p></div></div>
          <div class="answer-toolbar"><span>{evidence.length} / 8 excerpts in the evidence packet</span><button class="primary-button" disabled={modelState !== 'ready' || !evidence.length || answering} onclick={generate}><Icon name="spark" />Draft a comparison</button>{#if answering}<button class="subtle-button" onclick={stop}>Stop</button>{/if}</div>
          {#if modelState !== 'ready'}<p class="source-caption">You can read all evidence now. Load the browser model to draft a cited comparison.</p>{/if}
          {#if answer || answering}
            <div class="research-answer"><div class="section-label">AI DRAFT · VERIFY AGAINST THE SOURCES<span>{answering ? 'Writing locally…' : model?.title}</span></div>
              {#if !visibleAnswer}<p class="loading">{answering?'Preparing a comparison…':'The model returned no final answer. Try fewer excerpts or a narrower question.'}</p>{/if}
              {#each visibleAnswer.split('\n').filter(Boolean) as line}
                {#if /^#{1,4}\s/.test(line)}<h3>{line.replace(/^#{1,4}\s/,'').replace(/\*\*/g,'')}</h3>
                {:else}<p>{#each line.replace(/\*\*/g,'').split(/(\[S\d+\])/g) as part}{#if /^\[S\d+\]$/.test(part)}<a class:invalid-citation={audit.unknown.includes(part)} href={`#evidence-${part.slice(1,-1)}`}>{part}</a>{:else}{part}{/if}{/each}</p>{/if}
              {/each}
            </div>
            <div class="attribution-audit"><h3><Icon name="check" />Attribution check</h3><p>{audit.unknown.length ? `Unresolved citation identifiers: ${audit.unknown.join(', ')}. This draft needs correction.` : audit.hasCitations ? `${audit.cited.length} citation identifiers match the evidence packet.` : 'The draft has no source citations yet.'} This is an identifier check, not proof that the sources support the claims.</p><ul><li>Does the author endorse this view, or describe someone else’s?</li><li>Does the excerpt support the whole claim, including qualifications?</li><li>Are missing traditions and contested conclusions acknowledged?</li></ul></div>
          {/if}
          <div class="section-label">VERIFY FOR YOURSELF<span>CHECK UP TO 8 EXCERPTS FOR THE DRAFT</span></div>
          <div class="evidence-list">{#each results as result}{@const selectedEvidence = evidence.find(e => e.id === result.id)}<article class="evidence-card" id={selectedEvidence ? `evidence-${selectedEvidence.citation.slice(1,-1)}` : undefined}><div class="evidence-heading"><label><input type="checkbox" checked={included.includes(result.id)} disabled={answering || (!included.includes(result.id) && included.length >= 8)} onchange={() => toggleEvidence(result.id)} /><span>{selectedEvidence?.citation || 'Add'}</span></label><span class="tradition-badge">{result.tradition}</span>{#if result.editorial}<span class="outline-badge">Editorial summary</span>{/if}</div><h3>{result.title}</h3><p class="evidence-meta">{result.author} · {result.perspective}{#if result.publicationDate} · {result.publicationDate}{/if}<br>{result.locator}</p><blockquote>{evidenceExcerpt(result.text,submitted,850)}</blockquote><div class="inline-actions">{#if result.ref}<button class="subtle-button" onclick={() => onNavigate(result.ref,result.edition || 'BSB')}>Read passage<Icon name="arrow-right" /></button>{:else if result.articleId}<button class="subtle-button" onclick={() => onArticle(result.articleId)}>Read study article<Icon name="arrow-right" /></button>{/if}{#if result.sourceUrl}<a class="subtle-button" href={result.sourceUrl} target="_blank" rel="noreferrer">Original source ↗</a>{/if}<details><summary>Full indexed passage</summary><p class="full-evidence">{result.text}</p><p class="source-caption">{result.license}</p></details></div></article>{/each}</div>
        {/if}
      {/if}
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
    <aside class="research-sidebar">
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
    </aside>
  </div>
</section>
