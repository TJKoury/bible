import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {
  createIndex, dossierDocuments, evidenceExcerpt, isResearchContent, matchesPassage,
  parsePassages, prepareResearchDocuments, queryTerms, readingContextMatches, searchIndex, tokens,
} from '../src/lib/retrieval.js';

const read = path => JSON.parse(fs.readFileSync(new URL(`../public/data/${path}`, import.meta.url)));
const manifest = read('research/manifest.json');
const sourceById = new Map(manifest.sources.map(source => [source.id,source]));
const raw = read('research/chunks.json').map(chunk => ({...sourceById.get(chunk.sourceId),...chunk}));
const historical = prepareResearchDocuments(raw);
const documents = [...historical];
for (const book of read('catalog.json').books.filter(book => book.id <= 66)) {
  for (const [chapter,verses] of Object.entries(read(`translations/BSB/${book.id}.json`))) {
    const entries = Object.entries(verses);
    for (let start=0;start<entries.length;start+=3) {
      const group=entries.slice(start,start+3);
      const ref=`${book.id}.${chapter}.${group[0][0]}`;
      documents.push({id:`bible-${ref}`,sourceId:`bible-${book.id}`,ref,title:`${book.name} ${chapter}:${group[0][0]}–${group.at(-1)[0]}`,tradition:'Biblical texts',text:group.map(([verse,text])=>`${verse} ${text}`).join(' ')});
    }
  }
}
for (const dossier of read('research/dossiers.json')) documents.push(...dossierDocuments(dossier));
for (const article of read('encyclopedia/index.json').articles) documents.push({id:`wiki-${article.id}`,sourceId:`wiki-${article.id}`,articleId:article.id,title:article.title,tradition:'Encyclopedia',text:article.summary || article.description || article.title});
const index = createIndex(documents);

test('passage parsing preserves numbered books, compact references and verse ranges', () => {
  const refs=parsePassages('Compare John1:1 with 1 John 1:1–3 and Romans 9.');
  assert.deepEqual(refs.map(({book,chapter,verse,endVerse})=>({book,chapter,verse,endVerse})),[
    {book:43,chapter:1,verse:1,endVerse:null},
    {book:62,chapter:1,verse:1,endVerse:3},
    {book:45,chapter:9,verse:null,endVerse:null},
  ]);
  assert.equal(matchesPassage({text:'See 1 John 1:1.'},parsePassages('John 1:1')[0]),false);
  assert.equal(matchesPassage({text:'In the beginning was the Word. John i. 1.'},parsePassages('John 1:1')[0]),true);
});

test('comparison instructions and religion names do not replace the actual topic', () => {
  assert.deepEqual(queryTerms('Compare interpretations of John 1:1 across relevant traditions.'),[]);
  assert.deepEqual(queryTerms('Compare mercy across Christianity, Judaism and Islam.'),['mercy']);
  assert.deepEqual(queryTerms('Compare mercy across Jewish, Christian and Muslim sources. Identify each named author and cite the sources correctly.'),['mercy']);
  assert.deepEqual(queryTerms('Does Romans 9 teach individual election or corporate election?'),['individual','election','corporate']);
  assert.ok(tokens('merciful').includes('mercy'));
  assert.ok(!tokens('mercy seat').includes('mercy'));
});

test('full-corpus John comparison retrieves the verse and actual Word discussions', () => {
  const results=searchIndex(index,'Compare interpretations of John 1:1 across relevant traditions.',{limit:16});
  assert.equal(results[0].id,'bible-43.1.1');
  assert.ok(results.some(doc=>doc.id==='philaret-catechism:26'));
  assert.ok(results.some(doc=>doc.id==='augustine-confessions:143'));
  assert.ok(results.every(doc=>/in the beginning was the word/i.test(doc.text)),results.map(doc=>doc.id).join(', '));
  assert.ok(!results.some(doc=>doc.id==='kohler-theology:487'));
});

test('mercy comparison retrieves substantive material across the three religions', () => {
  const results=searchIndex(index,'Compare mercy across Christianity, Judaism and Islam.',{limit:16});
  for (const tradition of ['Christianity','Judaism','Islam']) {
    assert.ok(results.some(doc=>doc.tradition===tradition),`Missing relevant ${tradition} material`);
  }
  assert.ok(results.every(doc=>tokens(doc.text).includes('mercy')));
  assert.ok(!results.some(doc=>['ameer-ali-islam:15','ameer-ali-islam:20','kohler-theology:459'].includes(doc.id)));
  assert.ok(results.some(doc=>doc.sourceId==='quran-pickthall'));
  assert.ok(results.some(doc=>doc.id==='kohler-theology:117'));
  const filtered=searchIndex(index,'Compare mercy across Christianity, Judaism and Islam.',{traditions:['Judaism'],limit:8});
  assert.ok(filtered.length>0 && filtered.every(doc=>doc.tradition==='Judaism'));
});

test('Romans 9 keeps opposing positions and excludes unrelated institutional elections', () => {
  const results=searchIndex(index,'Does Romans 9 teach individual election or corporate election?',{limit:16});
  assert.ok(results.some(doc=>doc.sourceId==='schreiner-1993'));
  assert.ok(results.some(doc=>doc.sourceId==='abasciano-2006'));
  assert.ok(results.some(doc=>doc.ref?.startsWith('45.9.')));
  assert.ok(!results.some(doc=>doc.id==='calvin-institutes-2:382'));
  assert.match(results.find(doc=>doc.sourceId==='hagopian-2005').text,/survey/i);
});

test('a named-author follow-up puts Hagopian first while retaining the Romans 9 context', () => {
  const previous='How do Schreiner and Abasciano disagree about election in Romans 9?';
  const currentQuestion='What about Hagopian?';
  const results=searchIndex(index,`${previous}\n${currentQuestion}`,{limit:16,currentQuestion});
  assert.equal(results[0].sourceId,'hagopian-2005');
  assert.match(results[0].text,/survey/i);
  assert.equal(results[0].editorial,true);
  assert.ok(results.some(doc=>doc.ref?.startsWith('45.9.')));
  assert.ok(results.some(doc=>doc.sourceId==='schreiner-1993'));
  assert.ok(results.some(doc=>doc.sourceId==='abasciano-2006'));
  assert.equal(searchIndex(index,`${previous}\n${currentQuestion}`,{limit:1,currentQuestion})[0].sourceId,'hagopian-2005');
  assert.deepEqual(searchIndex(index,previous,{currentQuestion:previous}),searchIndex(index,previous));
});

test('current-topic priority does not bypass contextual relevance or force other traditions', () => {
  const previous='Compare mercy across Christianity, Judaism and Islam.';
  const currentQuestion='What about Judaism?';
  const results=searchIndex(index,`${previous}\n${currentQuestion}`,{limit:16,currentQuestion});
  assert.equal(results[0].tradition,'Judaism');
  assert.ok(results.every(doc=>tokens(doc.text).includes('mercy')));
  assert.ok(results.some(doc=>doc.tradition==='Islam'));
  assert.ok(results.some(doc=>doc.tradition==='Christianity'));
});

test('index excludes advertisements, tables of contents and detached note lists', () => {
  for (const id of ['ameer-ali-islam:15','ameer-ali-islam:20','kohler-theology:2','kohler-theology:459','kohler-theology:487']) {
    const doc=raw.find(doc=>doc.id===id);
    assert.ok(doc,`Missing fixture ${id}`);
    assert.equal(isResearchContent(doc),false,id);
    assert.ok(!index.documents.some(doc=>doc.id===id));
  }
});

test('Aquinas objections retain their response and explicit source-role warning', () => {
  const joined=historical.find(doc=>doc.id==='aquinas-god:298');
  assert.deepEqual(joined.sourceChunkIds,['aquinas-god:298','aquinas-god:299']);
  assert.ok(joined.text.includes(raw.find(doc=>doc.id==='aquinas-god:298').text));
  assert.ok(joined.text.includes(raw.find(doc=>doc.id==='aquinas-god:299').text));
  assert.match(joined.text,/I answer that/);
  assert.match(joined.roleWarning,/not necessarily Aquinas/);
  const results=searchIndex(index,'mercy',{limit:16}).filter(doc=>doc.sourceId==='aquinas-god');
  const ids=results.flatMap(doc=>doc.sourceChunkIds);
  assert.equal(new Set(ids).size,ids.length,'Joined passages must not be selected twice');
});

test('reading context follows generic requests but cannot override another question', () => {
  const context={ref:'43.1.1',passageText:documents.find(doc=>doc.id==='bible-43.1.1').text};
  assert.equal(readingContextMatches('Explain this passage.',context),true);
  assert.equal(readingContextMatches('Compare interpretations of John 1:1 across relevant traditions.',context),true);
  assert.equal(readingContextMatches('Does Romans 9 teach individual election?',context),false);
  assert.equal(readingContextMatches('Compare mercy across Christianity, Judaism and Islam.',context),false);
  assert.equal(readingContextMatches('John 1:44',context),false);
});

test('diversity does not promote a source with only a metadata or instruction-word match', () => {
  const small=createIndex([
    {id:'c',sourceId:'c',tradition:'Christianity',text:'Mercy is shown to the poor and the suffering.'},
    {id:'j',sourceId:'j',tradition:'Judaism',title:'Mercy',text:'This chapter lists the books and their authors.'},
    {id:'i',sourceId:'i',tradition:'Islam',text:'Across the river, the tradition was established.'},
  ]);
  assert.deepEqual(searchIndex(small,'Compare mercy across relevant traditions.').map(doc=>doc.id),['c']);
  assert.deepEqual(searchIndex(index,'unfindablewordxyz'),[]);
});

test('display excerpt preserves source whitespace and focuses on the requested reference', () => {
  const doc=historical.find(doc=>doc.id==='philaret-catechism:26');
  const excerpt=evidenceExcerpt(doc.text,'Compare interpretations of John 1:1 across relevant traditions.',850);
  assert.match(excerpt,/In the beginning was the Word/);
  assert.ok(doc.text.includes(excerpt.replace(/^… /,'').replace(/ …$/,'')));
  const paragraphs='Introduction sentence.\n\nA sentence about mercy.\n\nMercy continues here.\n\nUnrelated closing sentence. '.repeat(20);
  const quote=evidenceExcerpt(paragraphs,'mercy',140);
  assert.ok(paragraphs.includes(quote.replace(/^… /,'').replace(/ …$/,'')));
});

test('research worker keeps explicit passage context and excludes an unrelated current reading', async () => {
  const previousFetch=globalThis.fetch;
  const previousSelf=globalThis.self;
  const messages=[];
  globalThis.fetch=async path => {
    try {
      const data=JSON.parse(fs.readFileSync(new URL(`../public${new URL(path,'http://localhost/').pathname}`,import.meta.url)));
      return {ok:true,json:async()=>data};
    } catch { return {ok:false,status:404}; }
  };
  globalThis.self={location:{href:'http://localhost/research.worker.js'},postMessage:message=>messages.push(message)};
  try {
    await import('../src/lib/research.worker.js');
    const context={key:'BSB/43.1.1',ref:'43.1.1',book:43,chapter:1,verse:1,label:'John 1:1',edition:'BSB',editionTitle:'Berean Standard Bible',passageText:documents.find(doc=>doc.id==='bible-43.1.1').text};
    for (const [request,question,currentQuestion] of [
      ['john','Compare interpretations of John1:1 across relevant traditions.'],
      ['mercy','Compare mercy across Christianity, Judaism and Islam.'],
      ['romans','Does Romans 9 teach individual election or corporate election?'],
      ['context','Explain this passage.'],
      ['hagopian','How do Schreiner and Abasciano disagree about election in Romans 9?\nWhat about Hagopian?','What about Hagopian?'],
    ]) {
      await self.onmessage({data:{type:'search',request,question,currentQuestion,context,traditions:[]}});
    }
    assert.ok(!messages.some(message=>message.type==='error'),JSON.stringify(messages.filter(message=>message.type==='error')));
    const results=Object.fromEntries(messages.filter(message=>message.type==='results').map(message=>[message.request,message.results]));
    assert.equal(results.john[0].id,'reading-BSB/43.1.1');
    assert.equal(results.john.filter(doc=>doc.ref?.startsWith('43.1.')).length,1);
    assert.ok(!results.mercy.some(doc=>doc.id.startsWith('reading-')));
    assert.ok(!results.romans.some(doc=>doc.id.startsWith('reading-')));
    assert.ok(results.romans[0].ref.startsWith('45.9.'));
    assert.match(results.romans[0].text,/election/i);
    assert.equal(results.context[0].id,'reading-BSB/43.1.1');
    assert.ok(results.mercy.find(doc=>doc.sourceId==='aquinas-god').roleWarning);
    assert.equal(results.hagopian[0].sourceId,'hagopian-2005');
    assert.match(results.hagopian[0].text,/survey/i);
    assert.ok(results.hagopian.some(doc=>doc.ref?.startsWith('45.9.')));
  } finally {
    globalThis.fetch=previousFetch;
    if (previousSelf === undefined) delete globalThis.self;
    else globalThis.self=previousSelf;
  }
});
