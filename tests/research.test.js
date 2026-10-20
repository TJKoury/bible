import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createIndex, searchIndex, citationAudit, selectEvidence, evidenceExcerpt, tokens, dossierDocuments, normalizeCitations } from '../src/lib/retrieval.js';
import { passagePlaces, mapPoints, linkedArticles } from '../src/lib/geography.js';
import { buildMessages } from '../src/lib/ai.js';
const read = path => JSON.parse(fs.readFileSync(new URL(`../public/data/${path}`, import.meta.url)));

test('Bethsaida in John 1:44 preserves competing identifications', () => {
  const geo = read('geography/index.json');
  const places = passagePlaces(geo,43,1,44,'verse');
  const bethsaida = places.find(p => p.name === 'Bethsaida');
  assert.ok(bethsaida);
  const points = mapPoints([bethsaida]);
  assert.ok(points.some(p => /Araj/i.test(p.name)));
  assert.ok(points.some(p => /Tell/i.test(p.name)));
  assert.ok(points.every(p => p.disputed));
  assert.deepEqual(passagePlaces(geo,99,999,999,'verse'),[]);
  assert.equal(mapPoints([{id:'x',name:'Unknown',candidates:[{lat:null,lon:null}]}]).length,0);
});

test('entity matching uses word boundaries and respects ambiguity exclusions', () => {
  const wiki = {articles:[{id:'x',title:'Bethsaida',aliases:['Bethsaida']},{id:'y',title:'John',aliases:['John'],autoLink:false}]};
  assert.deepEqual(linkedArticles(wiki,'John is from Bethsaida.').map(a=>a.id),['x']);
  assert.deepEqual(linkedArticles(wiki,'Bethsaidan'),[]);
});

test('retrieval does not confuse Romans with Roman, and empty searches abstain', () => {
  assert.notDeepEqual(tokens('Romans'),tokens('Roman'));
  const index = createIndex([
    {id:'correct',sourceId:'a',title:'Romans 9',tradition:'Biblical texts',text:'Election, mercy, and the promise.'},
    {id:'wrong',sourceId:'b',title:'Roman history',tradition:'Encyclopedia',text:'A Roman election selects a bishop.'},
  ]);
  assert.equal(searchIndex(index,'Romans 9')[0].id,'correct');
  assert.deepEqual(searchIndex(index,'unfindablewordxyz'),[]);
  assert.deepEqual(searchIndex(index,'the and of'),[]);
});

test('selected evidence retains relevant represented traditions within the limit', () => {
  const results = Array.from({length:9},(_,i)=>({id:`c${i}`,tradition:'Christianity'}));
  results.push({id:'j',tradition:'Judaism'},{id:'i',tradition:'Islam'});
  const picked = selectEvidence(results,8);
  assert.equal(picked.length,8);
  assert.ok(picked.includes('j') && picked.includes('i'));
});

test('citation validation flags fabricated identifiers without claiming entailment', () => {
  const result = citationAudit('A claim [S1]. A fabricated source [S99].',[{citation:'[S1]'}]);
  assert.deepEqual(result.unknown,['[S99]']);
  assert.equal(result.entailmentVerified,false);
  assert.equal(citationAudit('No source provided',[]).hasCitations,false);
  assert.equal(normalizeCitations('Claim (S1, S99).'), 'Claim [S1] [S99].');
  assert.deepEqual(citationAudit('Claim (S1, S99).',[{citation:'[S1]'}]).unknown,['[S99]']);
});

test('research corpus metadata and three religions remain explicit', () => {
  const manifest = read('research/manifest.json');
  const chunks = read('research/chunks.json');
  const sources = new Map(manifest.sources.map(s=>[s.id,s]));
  assert.deepEqual([...new Set(manifest.sources.map(s=>s.tradition))].sort(),['Christianity','Islam','Judaism']);
  assert.equal(new Set(chunks.map(c=>c.id)).size,chunks.length);
  for (const c of chunks) assert.ok(sources.has(c.sourceId) && c.locator && c.text.length > 0);
  for (const s of sources.values()) {
    assert.ok(s.sourceUrl && s.license && s.sha256 && s.perspective);
    assert.equal(chunks.filter(c=>c.sourceId===s.id).length,s.chunkCount);
  }
});

test('Romans dossier keeps conflicting author positions and exact source links', () => {
  const dossier = read('research/dossiers.json').find(d=>d.id==='romans-9-election');
  const sources = new Set(dossier.sources.map(s=>s.id));
  assert.ok(dossier.positions.some(p=>p.id==='schreiner'));
  assert.ok(dossier.positions.some(p=>p.id==='abasciano'));
  for (const position of dossier.positions) for (const evidence of position.evidence) assert.ok(sources.has(evidence.sourceId));
  assert.match(dossier.positions.find(p=>p.id==='abasciano').summary,/distinguishes.*unconditional/i);
  assert.ok(dossier.sources.every(s=>s.fullTextIncluded===false));
  const documents = dossierDocuments(dossier);
  const original = documents.find(d => d.sourceId === 'schreiner-1993');
  const reply = documents.find(d => d.sourceId === 'schreiner-2006');
  assert.doesNotMatch(original.text, /His reply accepts/);
  assert.match(reply.text, /His reply accepts/);
  assert.match(reply.sourceUrl, /373-386/);
});

test('prompt preserves source roles and treats source content as data', () => {
  const messages = buildMessages('What does this author endorse?', [{citation:'[S1]',title:'A survey',editorial:true,excerpt:'An opponent proposes a view.'}]);
  assert.match(messages[0].content,/survey or quotation.*endorsement/i);
  assert.match(messages[0].content,/without endorsing or privileging any one tradition/i);
  assert.match(messages[1].content,/Editorial summary/);
  assert.match(evidenceExcerpt('A sentence about artifacts. '.repeat(80),'artifacts',100),/…$/);
});
