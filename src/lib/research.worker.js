import { createIndex, searchIndex, dossierDocuments } from './retrieval.js';
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
  const documents = chunks.map(c => ({ ...sources[c.sourceId], ...c, sourceId: c.sourceId, sourceUrl: sources[c.sourceId]?.sourceUrl }));
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
  return { count:documents.length, manifest };
}
self.onmessage = async ({data}) => {
  try {
    if (!setup) setup = load().catch(e => { setup = null; throw e; });
    const metadata = await setup;
    if (data.type === 'init') { self.postMessage({type:'ready', ...metadata}); return; }
    if (data.type === 'search') {
      let result = searchIndex(index, data.question, {traditions:data.traditions,limit:16});
      // A question with an explicit passage also retrieves its actual text.
      const normalized = data.question.toLowerCase();
      const matching = catalog.books.find(b => b.id <= 66 && new RegExp(`\\b${b.name.toLowerCase()}\\s+\\d+`).test(normalized));
      if (matching && data.context?.aligned !== false && (!data.traditions.length || data.traditions.includes('Biblical texts'))) {
        const [,chapter,verse] = normalized.match(new RegExp(`\\b${matching.name.toLowerCase()}\\s+(\\d+)(?::(\\d+))?`)) || [];
        const chapterDocs = index.documents.filter(d => d.ref?.startsWith(`${matching.id}.${chapter}.`));
        const exact = verse ? chapterDocs.find(d => { const v = Number(d.ref.split('.')[2]); return Number(verse) >= v && Number(verse) < v + 3; }) : chapterDocs[0];
        const ranked = searchIndex(createIndex(chapterDocs), data.question.replace(new RegExp(`${matching.name}\\s+\\d+(?::\\d+)?`,'i'),''), {limit:2,diverse:false});
        const explicit = [exact,...ranked].filter((d,i,a)=>d && a.findIndex(v=>v?.id === d.id) === i);
        const contextual = explicit.map(doc => {
          const position = chapterDocs.findIndex(d => d.id === doc.id);
          const neighbors = chapterDocs.slice(Math.max(0,position-1),position+2);
          const first = neighbors[0];
          const lastVerse = neighbors.at(-1).title.match(/(?:–|:)(\d+)$/)?.[1];
          return {...doc, ref:first.ref, title:`${matching.name} ${chapter}:${first.ref.split('.')[2]}–${lastVerse}`, text:neighbors.map(d=>d.text).join(' ')};
        });
        result = [...contextual, ...result.filter(d => !explicit.some(e => e.id === d.id))].slice(0, 16);
      }
      // Fetch actual retained sections only for encyclopedic hits in this search.
      result = await Promise.all(result.map(async doc => {
        if (!doc.articleId) return doc;
        try {
          const article = await get(`/data/encyclopedia/articles/${encodeURIComponent(doc.articleId)}.json`);
          const sections = article.sections.map((s,i)=>({...doc,id:`${doc.id}-${i}`,text:s.text,heading:s.title,locator:s.title}));
          const best = searchIndex(createIndex(sections),data.question,{limit:1,diverse:false})[0];
          return best ? {...best,sourceUrl:article.revisionUrl} : doc;
        } catch { return doc; }
      }));
      if(data.context?.passageText && (!data.traditions.length || data.traditions.includes('Biblical texts'))) {
        const ctx=data.context;
        const current={id:`reading-${ctx.key}`,sourceId:`reading-${ctx.edition}-${ctx.book}`,title:`${ctx.label} · surrounding passage`,author:ctx.book<=39?'Hebrew Bible':'Biblical text',tradition:'Biblical texts',perspective:ctx.editionTitle,ref:ctx.ref,edition:ctx.edition,locator:`Current reading · ${ctx.edition}`,text:ctx.passageText,sourceUrl:new URL(assetUrl(`/data/translations/${ctx.edition}/${ctx.book}.json`),self.location.href).href,license:catalog.translations.find(t=>t.id===ctx.edition)?.license};
        result=[current,...result].slice(0,16);
      }
      self.postMessage({type:'results',request:data.request,results:result});
    }
  } catch (e) { self.postMessage({type:'error',request:data.request,message:e.message}); }
};
