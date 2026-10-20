import { createIndex, searchIndex, dossierDocuments, prepareResearchDocuments, parsePassages, matchesPassage, queryTerms, readingContextMatches, prioritizeCurrentQuestion } from './retrieval.js';
import { assetUrl } from './data.js';
let index;
let catalog;
let setup;
async function get(path) { const response = await fetch(assetUrl(path)); if (!response.ok) throw new Error(`Could not load ${path}`); return response.json(); }
async function load() {
  const [manifest, chunks, books, encyclopedia] = await Promise.all([
    get('/data/research/manifest.json'), get('/data/research/chunks.json'), get('/data/catalog.json'), get('/data/encyclopedia/index.json'),
  ]);
  catalog = books;
  const sources = Object.fromEntries(manifest.sources.map(s => [s.id, s]));
  const documents = prepareResearchDocuments(chunks.map(c => ({ ...sources[c.sourceId], ...c, sourceId: c.sourceId, sourceUrl: sources[c.sourceId]?.sourceUrl })));
  self.postMessage({ type: 'progress', text: 'Indexing the biblical texts…' });
  for (let start = 1; start <= 66; start += 8) {
    const ids = Array.from({length: Math.min(8, 67-start)},(_,i) => start+i);
    const values = await Promise.all(ids.map(id => get(`/data/translations/BSB/${id}.json`)));
    ids.forEach((book, i) => {
      const name = books.books.find(b => b.id === book).name;
      for (const [chapter, verses] of Object.entries(values[i])) {
        const rows = Object.entries(verses);
        for (let v = 0; v < rows.length; v += 3) {
          const group = rows.slice(v, v + 3);
          const ref = `${book}.${chapter}.${group[0][0]}`;
          documents.push({ id: `bible-${ref}`, sourceId: `bible-${book}`, title: `${name} ${chapter}:${group[0][0]}${group.length > 1 ? `–${group.at(-1)[0]}` : ''}`, author: book <= 39 ? 'Hebrew Bible' : 'New Testament', tradition: 'Biblical texts', perspective: 'BSB English translation', license: 'Public domain', sourceUrl: 'https://berean.bible/', ref, locator: `${name} ${chapter}`, text: group.map(([v,t]) => `${v} ${t}`).join(' ') });
        }
      }
    });
  }
  // One entry per downloaded encyclopedia section; full text remains on demand.
  const wiki = Array.isArray(encyclopedia.articles) ? encyclopedia.articles : Object.values(encyclopedia.articles || {});
  for (const a of wiki) {
    documents.push({ id: `wiki-${a.id}`, sourceId: `wiki-${a.id}`, articleId:a.id, title:a.title, author:'Wikipedia contributors', tradition:'Encyclopedia', perspective:'Reference overview; claims may be disputed', sourceUrl:a.revisionUrl || a.url, license:'CC BY-SA 4.0', locator:'Article summary', text:a.summary || a.description || a.title });
  }
  // Dossiers contain short editorial summaries and original source links, not downloaded papers.
  try {
    const dossiers = await get('/data/research/dossiers.json');
    const items = Array.isArray(dossiers) ? dossiers : dossiers.dossiers || [];
    for (const dossier of items) documents.push(...dossierDocuments(dossier));
  } catch { /* Optional dossier; the downloaded primary-source index remains usable. */ }
  self.postMessage({ type:'progress', text:'Building the local source index…' });
  index = createIndex(documents);
  return { count:index.documents.length, manifest };
}
self.onmessage = async ({data}) => {
  try {
    if (!setup) setup = load().catch(e => { setup = null; throw e; });
    const metadata = await setup;
    if (data.type === 'init') { self.postMessage({type:'ready', ...metadata}); return; }
    if (data.type === 'search') {
      const traditions = data.traditions || [];
      // An otherwise generic "explain this passage" follows the current reading.
      // An explicit topic or reference is allowed to leave that reading context.
      const question = !parsePassages(data.question).length && !queryTerms(data.question).length && data.context?.label
        ? `${data.question} ${data.context.label}` : data.question;
      const currentQuestion = typeof data.currentQuestion === 'string' && data.currentQuestion.trim() !== data.question.trim() ? data.currentQuestion : '';
      let result = searchIndex(index, question, {traditions,limit:16,currentQuestion});
      const references = parsePassages(question, catalog.books.filter(book => book.id <= 66));
      if (!traditions.length || traditions.includes('Biblical texts')) {
        const contextual = [];
        const included = new Set();
        for (const reference of references) {
          const chapterDocs = index.documents.filter(doc => doc.ref?.startsWith(`${reference.book}.${reference.chapter}.`));
          const doc = result.find(hit => hit.ref && matchesPassage(hit,reference));
          if (!doc || included.has(doc.id)) continue;
          const position = chapterDocs.findIndex(hit => hit.id === doc.id);
          const neighbors = chapterDocs.slice(Math.max(0,position-1),position+2);
          const first = neighbors[0];
          const lastVerse = neighbors.at(-1).title.match(/(?:–|:)(\d+)$/)?.[1];
          neighbors.forEach(hit => included.add(hit.id));
          contextual.push({...doc, ref:first.ref, title:`${reference.name} ${reference.chapter}:${first.ref.split('.')[2]}–${lastVerse}`, locator:`${reference.name} ${reference.chapter}`, text:neighbors.map(hit=>hit.text).join(' ')});
        }
        result = [...contextual, ...result.filter(doc => !included.has(doc.id))].slice(0,16);
      }
      // Fetch actual retained sections only for encyclopedic hits in this search.
      result = await Promise.all(result.map(async doc => {
        if (!doc.articleId) return doc;
        try {
          const article = await get(`/data/encyclopedia/articles/${encodeURIComponent(doc.articleId)}.json`);
          const sections = article.sections.map((s,i)=>({...doc,id:`${doc.id}-${i}`,text:s.text,heading:s.title,locator:s.title}));
          const best = searchIndex(createIndex(sections),question,{limit:1,diverse:false,currentQuestion})[0];
          return best ? {...best,sourceUrl:article.revisionUrl} : doc;
        } catch { return doc; }
      }));
      if(readingContextMatches(data.question,data.context) && (!traditions.length || traditions.includes('Biblical texts'))) {
        const ctx=data.context;
        const current={id:`reading-${ctx.key}`,sourceId:`reading-${ctx.edition}-${ctx.book}`,title:`${ctx.label} · surrounding passage`,author:ctx.book<=39?'Hebrew Bible':'Biblical text',tradition:'Biblical texts',perspective:ctx.editionTitle,ref:ctx.ref,edition:ctx.edition,locator:`Current reading · ${ctx.edition}`,text:ctx.passageText,sourceUrl:new URL(assetUrl(`/data/translations/${ctx.edition}/${ctx.book}.json`),self.location.href).href,license:catalog.translations.find(t=>t.id===ctx.edition)?.license};
        // Replace the same retrieved passage instead of citing two editions as
        // independent support for an otherwise identical context window.
        const [book,chapter,verse] = ctx.ref.split('.').map(Number);
        result=[current,...result.filter(doc => !doc.ref || !matchesPassage(doc,{book,chapter,verse}))].slice(0,16);
      }
      result = prioritizeCurrentQuestion(result,currentQuestion);
      self.postMessage({type:'results',request:data.request,results:result});
    }
  } catch (e) { self.postMessage({type:'error',request:data.request,message:e.message}); }
};
