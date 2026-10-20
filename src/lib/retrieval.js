const stopWords = new Set('a an and are as at be been being but by can could did do does for from had has have he her him his how i if in into is it its may more most no not of on or our ought shall she should so than that the their them then there these they this those to was we were what when where which who why will with would you your teach teaches about say says according compare across between among please'.split(' '));
const unstemmed = new Set(['romans','hebrews','james','acts','judges','numbers','psalms','kings','chronicles','ephesians','galatians','philippians','colossians']);
const bookNames = 'Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|1 Samuel|2 Samuel|1 Kings|2 Kings|1 Chronicles|2 Chronicles|Ezra|Nehemiah|Esther|Job|Psalms|Proverbs|Ecclesiastes|Song of Solomon|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|Romans|1 Corinthians|2 Corinthians|Galatians|Ephesians|Philippians|Colossians|1 Thessalonians|2 Thessalonians|1 Timothy|2 Timothy|Titus|Philemon|Hebrews|James|1 Peter|2 Peter|1 John|2 John|3 John|Jude|Revelation'.split('|');
const books = bookNames.map((name,index) => ({name,id:index+1}));
export function tokens(text) {
  return (String(text || '').toLowerCase().normalize('NFKD').replace(/\p{M}/gu, '').replace(/\bmercy[\s-]+seat\b/g, 'mercyseat').match(/[\p{L}\p{N}]+/gu) || [])
    .filter(t => t.length > 1 && !stopWords.has(t))
    .map(t => t === 'mercies' || t === 'merciful' ? 'mercy' : t.length > 5 && !unstemmed.has(t) ? t.replace(/(ing|ed|s)$/, '') : t);
}
const instructionWords = new Set(tokens('compare comparison comparisons interpret interpretation interpretations understand understanding explain explanation relevant different tradition traditions perspective perspectives viewpoint viewpoints view views belief beliefs meaning mean means discuss describe discussion teaching teachings scripture scriptural biblical passage passages verse verses context help helps named author authors source sources cite cited citation citations attribute attribution each every rather question answer answers identify correctly'));
const traditionWords = new Set(tokens('Christian Christianity Christians Jewish Judaism Jews Islam Islamic Muslim Muslims Catholic Catholicism Protestant Protestantism Orthodox Orthodoxy interfaith religions religious'));
const escapeRegex = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
export function parsePassages(question, availableBooks = books) {
  const matches = [];
  for (const book of availableBooks) {
    const pattern = new RegExp(`\\b${escapeRegex(book.name).replace(/ /g, '\\s+')}\\s*(\\d{1,3})(?:\\s*:\\s*(\\d{1,3})(?:\\s*[-–]\\s*(\\d{1,3}))?)?\\b`, 'gi');
    for (const match of question.matchAll(pattern)) {
      // "John 1" inside "1 John 1" must not become the Gospel of John.
      if (!/^\d/.test(book.name) && /\b[1-3]\s*$/.test(question.slice(0,match.index))) continue;
      matches.push({book:book.id,name:book.name,chapter:Number(match[1]),verse:match[2] ? Number(match[2]) : null,endVerse:match[3] ? Number(match[3]) : null,start:match.index,end:match.index+match[0].length});
    }
  }
  return matches.sort((a,b)=>a.start-b.start || b.end-a.end).filter((ref,i,all)=>!all.slice(0,i).some(other=>ref.start>=other.start && ref.end<=other.end));
}
export function queryTerms(question) {
  let content = String(question || '');
  for (const ref of parsePassages(content).reverse()) content = content.slice(0,ref.start) + ' ' + content.slice(ref.end);
  const raw = [...new Set(tokens(content))].filter(word => !/^\d+$/.test(word));
  const topical = raw.filter(word => !instructionWords.has(word) && !traditionWords.has(word));
  // Tradition names describe whose positions to compare, not the topic of the positions.
  return topical.length ? topical : raw.filter(word => !instructionWords.has(word));
}
export function isResearchContent(doc) {
  const text = String(doc.text || '').trim();
  if (!text) return false;
  if (doc.ref || doc.articleId || doc.editorial || doc.sourceId === 'quran-pickthall') return true;
  if (doc.heading && text.toLowerCase() === doc.heading.trim().toLowerCase()) return false;
  if (text.split(/\s+/).length < 35 && /\n\s*\nBy\s+[A-Z]/.test(text)) return false;
  if ((text.match(/\bCHAPTER\s+(?:[IVXLCDM]+|\d+)\b/gi) || []).length >= 3 && /\b(?:contents|dedication|preface)\b/i.test(text)) return false;
  const lines=text.split(/\n+/).map(line=>line.trim()).filter(Boolean);
  if(lines.length>=4 && lines.filter(line=>/^_?\s*\d{1,4}[.)]?\s+/.test(line)).length/lines.length>=0.8 && text.split(/\s+/).length/lines.length<25)return false;
  return true;
}
export function prepareResearchDocuments(documents) {
  return documents.map((doc,index)=>{
    if(doc.sourceId!=='aquinas-god')return doc;
    const combined={...doc,sourceChunkIds:[doc.id],sourceRole:'Scholastic disputation',roleWarning:'Objection and Obj. introduce positions being examined, not necessarily Aquinas’s own view. I answer that gives his response; Reply Obj. answers an objection.'};
    if(!/(?:^|\n)(?:Objection\s+1|Obj\.\s+\d)/i.test(doc.text) || /I answer that/i.test(doc.text))return combined;
    for(let offset=1;offset<=2;offset++){
      const next=documents[index+offset];
      if(!next || next.sourceId!==doc.sourceId || next.heading!==doc.heading)break;
      combined.text+=`\n\n${next.text}`;combined.sourceChunkIds.push(next.id);
      combined.locator=`${doc.locator}; continuation through ${next.locator}`;
      if(/I answer that/i.test(next.text))break;
    }
    return combined;
  });
}
export function readingContextMatches(question, context) {
  if (!context?.passageText) return false;
  const references = parsePassages(question);
  const [book, chapter, verse] = String(context.ref || '').split('.').map(Number);
  if (references.length && !references.some(ref => ref.book === book && ref.chapter === chapter && (!ref.verse || verse >= ref.verse && verse <= (ref.endVerse || ref.verse)))) return false;
  const words = queryTerms(question);
  if (!words.length) return true;
  const body = new Set(tokens(context.passageText));
  const needed = Math.min(3, Math.max(1, Math.ceil(words.length / 2)));
  return words.filter(word => body.has(word)).length >= needed;
}
export function createIndex(documents) {
  documents = documents.filter(isResearchContent);
  const postings = new Map();
  const lengths = [];
  documents.forEach((doc,index) => {
    const body = tokens(doc.text);
    const metadata = tokens(`${doc.title || ''} ${doc.heading || ''} ${doc.locator || ''}`);
    lengths[index] = body.length;
    const counts = new Map();
    for (const word of body) { const count=counts.get(word) || [0,0];count[0]++;counts.set(word,count); }
    for (const word of metadata) { const count=counts.get(word) || [0,0];count[1]++;counts.set(word,count); }
    for (const [word,[bodyCount,metadataCount]] of counts) {
      if (!postings.has(word)) postings.set(word,[]);
      postings.get(word).push([index,bodyCount,metadataCount]);
    }
  });
  return {documents,postings,lengths,average:lengths.reduce((a,b)=>a+b,0)/(lengths.length || 1)};
}
function roman(number) {
  let value='';
  for (const [amount,symbol] of [[100,'c'],[90,'xc'],[50,'l'],[40,'xl'],[10,'x'],[9,'ix'],[5,'v'],[4,'iv'],[1,'i']]) while(number>=amount){value+=symbol;number-=amount;}
  return value;
}
function passagePattern(ref) {
  const chapter=`(?:${ref.chapter}|${roman(ref.chapter)})`;
  const verse=ref.verse ? `\\s*[:.,]\\s*${ref.verse}(?!\\d)` : '(?=[\\s:.,;)\\]]|$)';
  return new RegExp(`\\b${escapeRegex(ref.name).replace(/ /g,'\\s+')}\\s*${chapter}${verse}`,'gi');
}
export function matchesPassage(doc, ref) {
  if (doc.ref) {
    const [book,chapter,verse] = doc.ref.split('.').map(Number);
    const last = Number(doc.title?.match(/[-–](\d+)\s*$/)?.[1] || verse + 2);
    return book===ref.book && chapter===ref.chapter && (!ref.verse || (ref.verse<=last && (ref.endVerse || ref.verse)>=verse));
  }
  const pattern = passagePattern(ref);
  const text=`${doc.title || ''} ${doc.heading || ''} ${doc.text}`;
  return [...text.matchAll(pattern)].some(match => /^\d/.test(ref.name) || !/\b[1-3]\s*$/.test(text.slice(0,match.index)));
}
export function prioritizeCurrentQuestion(documents, currentQuestion) {
  const wanted = queryTerms(currentQuestion || '');
  if (!wanted.length) return documents;
  // Apply only to already relevant results. An author's name in a follow-up
  // identifies the requested voice; a prior author's mention of that name does
  // not make the prior author the focus of the new question.
  return documents.map((doc,order) => {
    const identity = new Set(tokens(`${doc.author || ''} ${doc.tradition || ''} ${doc.perspective || ''}`));
    const body = new Set(tokens(doc.text));
    const heading = new Set(tokens(`${doc.title || ''} ${doc.heading || ''}`));
    const identityMatches = wanted.filter(word=>identity.has(word)).length;
    const bodyMatches = wanted.filter(word=>body.has(word)).length;
    const headingMatches = wanted.filter(word=>heading.has(word)).length;
    const currentQuestionScore = (identityMatches*4 + bodyMatches + headingMatches*0.5)/wanted.length;
    return { doc:{...doc,currentQuestionScore}, order };
  }).sort((a,b)=>b.doc.currentQuestionScore-a.doc.currentQuestionScore || a.order-b.order).map(({doc})=>doc);
}
export function searchIndex(index, question, options = {}) {
  const currentQuestion = typeof options.currentQuestion === 'string' && options.currentQuestion.trim() !== question.trim() ? options.currentQuestion : '';
  const references=parsePassages(question,options.books || books);
  const primaryWords=queryTerms(question);
  const N=index.documents.length;
  const idfFor=word=>{const n=index.postings.get(word)?.length || 0;return Math.log(1+(N-n+0.5)/(n+0.5));};
  const anchors=new Set();
  if(references.length) index.documents.forEach((doc,id)=>{if(references.some(ref=>matchesPassage(doc,ref)))anchors.add(id);});
  let words=primaryWords;
  let expanded=false;
  let passagePhrases=[];
  if(!words.length && references.length){
    // A passage-only request uses its actual wording, never "across" or "interpretations".
    const passage=index.documents.filter((doc,id)=>doc.ref && anchors.has(id)).map(doc=>doc.text).join(' ');
    const frequencies=new Map();
    tokens(passage).filter(word=>!/^\d+$/.test(word)).forEach(word=>frequencies.set(word,(frequencies.get(word)||0)+1));
    words=[...frequencies].sort((a,b)=>idfFor(b[0])*Math.min(b[1],3)-idfFor(a[0])*Math.min(a[1],3)).slice(0,6).map(([word])=>word);
    const phraseWords=passage.toLowerCase().match(/\p{L}+/gu)||[];
    passagePhrases=[...new Set(phraseWords.slice(0,-4).map((_,i)=>phraseWords.slice(i,i+5).join(' ')))];
    expanded=true;
  }
  if(!words.length && !anchors.size)return [];
  const scores=new Map();
  const matched=new Map();
  const bodyMatched=new Map();
  for(const word of words){
    for(const [id,bodyTf,metadataTf] of index.postings.get(word) || []){
      const tf=bodyTf+Math.min(metadataTf,2)*0.6;
      const score=idfFor(word)*(tf*2.2)/(tf+1.2*(0.25+0.75*index.lengths[id]/(index.average||1)));
      scores.set(id,(scores.get(id)||0)+score);
      matched.set(id,(matched.get(id)||0)+1);
      if(bodyTf || index.documents[id].articleId)bodyMatched.set(id,(bodyMatched.get(id)||0)+1);
    }
  }
  const minimum=expanded ? Math.min(2,words.length) : Math.min(3,Math.max(1,Math.ceil(words.length/(references.length ? 1 : 2))));
  const bestScore=Math.max(1,...scores.values());
  for(const id of anchors)scores.set(id,(scores.get(id)||0)+bestScore*1.4);
  const candidates=[...scores].filter(([id])=>{
    if(anchors.has(id))return true;
    if((bodyMatched.get(id)||0)<minimum)return false;
    if(expanded){
      const text=(index.documents[id].text.toLowerCase().match(/\p{L}+/gu)||[]).join(' ');
      return passagePhrases.some(phrase=>text.includes(phrase));
    }
    return true;
  })
    .map(([id,score])=>({...index.documents[id],score:score*(anchors.has(id)?1:0.35+0.65*(matched.get(id)||0)/(words.length||1)),matched:matched.get(id)||0,passageMatch:anchors.has(id)}))
    .filter(doc=>!options.traditions?.length || options.traditions.includes(doc.tradition))
    .sort((a,b)=>b.score-a.score || a.id.localeCompare(b.id));
  // A diversity slot is available only after the same topical gate and score floor.
  const topicalBest=candidates.find(doc=>!doc.passageMatch)?.score || candidates[0]?.score || 0;
  const relevant=prioritizeCurrentQuestion(candidates.filter(doc=>doc.passageMatch || doc.score>=topicalBest*0.32),currentQuestion);
  const selected=[];const seen=new Set();const perSource=new Map();
  function add(doc){
    if(!doc || seen.has(doc.id) || (perSource.get(doc.sourceId || doc.id)||0)>=2)return;
    if(doc.sourceChunkIds && selected.some(other=>other.sourceId===doc.sourceId && other.sourceChunkIds?.some(id=>doc.sourceChunkIds.includes(id))))return;
    selected.push(doc);seen.add(doc.id);perSource.set(doc.sourceId || doc.id,(perSource.get(doc.sourceId || doc.id)||0)+1);
  }
  if(options.diverse!==false){
    const bestByTradition=new Map();
    relevant.forEach(doc=>{if(!bestByTradition.has(doc.tradition))bestByTradition.set(doc.tradition,doc);});
    prioritizeCurrentQuestion([...bestByTradition.values()].sort((a,b)=>b.score-a.score),currentQuestion).forEach(add);
  }
  for(const candidate of relevant){if(selected.length>=(options.limit||12))break;add(candidate);}
  return prioritizeCurrentQuestion(selected.slice(0,options.limit||12).sort((a,b)=>b.score-a.score),currentQuestion);
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
  const wanted = new Set(queryTerms(question));
  const sentences = [...text.matchAll(/[^.!?\n]+[.!?]?/g)];
  let best = 0, score = -1;
  sentences.forEach((sentence,i) => { const n = tokens(sentence[0]).filter(t => wanted.has(t)).length; if (n > score) { score = n; best = i; } });
  let start = sentences[Math.max(0,best-1)]?.index || 0;
  if (!wanted.size) {
    const anchor = parsePassages(question).map(ref => text.search(passagePattern(ref))).find(index => index >= 0);
    if (anchor !== undefined) {
      start = Math.max(0,anchor-Math.floor(maxLength*0.7));
      if (start) { const boundary=text.slice(start).search(/\s/);if(boundary>=0)start+=boundary+1; }
    }
  }
  let end = Math.min(text.length,start+maxLength);
  if (end < text.length) {
    const boundary=text.lastIndexOf(' ',end);
    if(boundary>start+maxLength*0.8)end=boundary;
  }
  return `${start > 0 ? '… ' : ''}${text.slice(start,end).trim()}${end < text.length ? ' …' : ''}`;
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
