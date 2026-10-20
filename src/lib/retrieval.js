const stopWords = new Set('a an and are as at be been being but by can could did do does for from had has have he her him his how i if in into is it its may more most no not of on or our ought shall she should so than that the their them then there these they this those to was we were what when where which who why will with would you your teach teaches about say says according compare'.split(' '));
const unstemmed = new Set(['romans','hebrews','james','acts','judges','numbers','psalms','kings','chronicles','ephesians','galatians','philippians','colossians']);
export function tokens(text) {
  return (text.toLowerCase().normalize('NFKD').replace(/\p{M}/gu, '').match(/[\p{L}\p{N}]+/gu) || [])
    .filter(t => t.length > 1 && !stopWords.has(t))
    .map(t => t.length > 5 && !unstemmed.has(t) ? t.replace(/(ing|ed|s)$/, '') : t);
}
export function createIndex(documents) {
  const postings = new Map();
  const lengths = [];
  documents.forEach((doc, index) => {
    const words = tokens(`${doc.title || ''} ${doc.heading || ''} ${doc.locator || ''} ${doc.text}`);
    lengths[index] = words.length;
    const counts = new Map();
    for (const word of words) counts.set(word, (counts.get(word) || 0) + 1);
    for (const [word, count] of counts) {
      if (!postings.has(word)) postings.set(word, []);
      postings.get(word).push([index, count]);
    }
  });
  return { documents, postings, lengths, average: lengths.reduce((a, b) => a + b, 0) / (lengths.length || 1) };
}
export function searchIndex(index, question, options = {}) {
  const words = [...new Set(tokens(question))];
  if (!words.length) return [];
  const scores = new Map();
  const matched = new Map();
  const N = index.documents.length;
  for (const word of words) {
    const rows = index.postings.get(word) || [];
    const idf = Math.log(1 + (N - rows.length + 0.5) / (rows.length + 0.5));
    for (const [id, tf] of rows) {
      const dl = index.lengths[id];
      const score = idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * dl / (index.average || 1)));
      scores.set(id, (scores.get(id) || 0) + score);
      matched.set(id, (matched.get(id) || 0) + 1);
    }
  }
  const candidates = [...scores].map(([id, score]) => ({ ...index.documents[id], score: score * (0.4 + 0.6 * matched.get(id) / words.length), matched: matched.get(id) }))
    .filter(d => !options.traditions?.length || options.traditions.includes(d.tradition))
    .sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
  // Relevance remains necessary; diversity never manufactures a missing position.
  const relevant = candidates.filter(d => d.score >= (candidates[0]?.score || 0) * 0.18);
  const selected = [];
  const seen = new Set();
  const perSource = new Map();
  function add(doc) {
    if (!doc || seen.has(doc.id) || (perSource.get(doc.sourceId) || 0) >= 2) return;
    selected.push(doc); seen.add(doc.id); perSource.set(doc.sourceId, (perSource.get(doc.sourceId) || 0) + 1);
  }
  if (options.diverse !== false) {
    const bestByTradition = new Map();
    relevant.forEach(d => { if (!bestByTradition.has(d.tradition)) bestByTradition.set(d.tradition, d); });
    [...bestByTradition.values()].sort((a,b) => b.score - a.score).forEach(add);
  }
  for (const candidate of relevant) {
    if (selected.length >= (options.limit || 12)) break;
    add(candidate);
  }
  return selected.slice(0, options.limit || 12).sort((a,b) => b.score - a.score);
}
export function normalizeCitations(answer) {
  // Format only: this neither invents references nor validates what they support.
  return answer.replace(/[\[(](S\d+(?:\s*,\s*S\d+)*)[\])]/g, (_, ids) =>
    ids.split(/\s*,\s*/).map(id => `[${id}]`).join(' '));
}
export function citationAudit(answer, evidence) {
  const valid = new Set(evidence.map(e => e.citation));
  const cited = [...new Set(normalizeCitations(answer).match(/\[S\d+\]/g) || [])];
  return {
    cited,
    unknown: cited.filter(id => !valid.has(id)),
    uncited: evidence.filter(e => !cited.includes(e.citation)).map(e => e.citation),
    hasCitations: cited.length > 0,
    // This checks references only. It cannot establish that a claim follows from them.
    entailmentVerified: false,
  };
}
export function selectEvidence(results, limit = 8) {
  const picked = [];
  const traditions = new Set();
  for (const result of results) {
    if (!traditions.has(result.tradition)) { picked.push(result.id); traditions.add(result.tradition); }
    if (picked.length === limit) return picked;
  }
  for (const result of results) {
    if (!picked.includes(result.id)) picked.push(result.id);
    if (picked.length === limit) break;
  }
  return picked;
}
export function evidenceExcerpt(text, question, maxLength = 850) {
  if (text.length <= maxLength) return text;
  const wanted = new Set(tokens(question));
  const sentences = text.match(/[^.!?\n]+[.!?]?/g) || [text];
  let best = 0, score = -1;
  sentences.forEach((s,i) => { const n = tokens(s).filter(t => wanted.has(t)).length; if (n > score) { score = n; best = i; } });
  let excerpt = sentences.slice(Math.max(0, best - 1)).join('').trim().slice(0, maxLength);
  const lastSpace = excerpt.lastIndexOf(' ');
  if (lastSpace > maxLength * 0.8) excerpt = excerpt.slice(0, lastSpace);
  return `${best > 1 ? '… ' : ''}${excerpt} …`;
}
// Keep claims tied to the particular work that was checked, including when one
// author's position is documented by several articles.
export function dossierDocuments(dossier) {
  return (dossier.positions || []).flatMap(position => {
    const sourceIds = [...new Set((position.evidence || []).map(e => e.sourceId))];
    return sourceIds.flatMap(id => {
      const source = dossier.sources.find(s => s.id === id);
      if (!source) return [];
      const evidence = position.evidence.filter(e => e.sourceId === id);
      return [{
        id: `dossier-${dossier.id}-${position.id}-${id}`,
        sourceId: id, title: source.title, author: source.author,
        tradition: position.tradition || 'Christianity', perspective: position.perspective,
        sourceUrl: source.url, license: 'Editorial summary; original article rights retained',
        locator: `${dossier.title} · ${evidence.map(e => e.locator).join('; ')}`,
        text: `${dossier.title}. ${(sourceIds.length === 1 ? position.summary : position.label).replace(/\.$/,'')}. ${evidence.map(e => `${e.claim} Attribution role: ${e.role}.`).join(' ')}`,
        editorial: true,
      }];
    });
  });
}
