import test from 'node:test';
import assert from 'node:assert/strict';
import { buildConversationContext, isFollowUp } from '../src/lib/conversation.js';
import { createIndex, queryTerms, searchIndex } from '../src/lib/retrieval.js';

const reading={key:'BSB/43.1.1',label:'John 1:1',ref:'43.1.1'};
const earlierReading={key:'BSB/45.9.1',label:'Romans 9:1',ref:'45.9.1'};
const history=[
  {id:'mercy',question:'Compare mercy across Christianity, Judaism and Islam.',context:earlierReading,answer:'Invented answer text must never become evidence.'},
  {id:'unrelated',question:'Where was Bethsaida?',context:reading},
  {id:'judaism',question:'What about Judaism?',parentId:'mercy',context:earlierReading},
  {id:'evidence',question:'Which sources support that?',parentId:'judaism',context:earlierReading},
  {id:'details',question:'Tell me more.',parentId:'evidence',context:earlierReading},
];

test('a follow-up uses the selected branch and its reading snapshot, not timeline neighbors', () => {
  const next=buildConversationContext('What about Judaism?',{history,selectedId:'mercy',context:reading});
  assert.equal(next.followUp,true);
  assert.equal(next.parentId,'mercy');
  assert.deepEqual(next.priorQuestionIds,['mercy']);
  assert.equal(next.context,earlierReading);
  assert.equal(next.searchQuestion,'Compare mercy across Christianity, Judaism and Islam.\nWhat about Judaism?');
  assert.deepEqual(queryTerms(next.searchQuestion),['mercy']);
  assert.match(next.selectionQuestion,/Current follow-up question:\nWhat about Judaism\?/);
  assert.doesNotMatch(next.searchQuestion,/Bethsaida|Invented answer/);
});

test('follow-up retrieval remains anchored to the previous topic', () => {
  const next=buildConversationContext('What about Judaism?',{history,selectedId:'mercy',context:reading});
  const index=createIndex([
    {id:'mercy',sourceId:'j1',tradition:'Judaism',text:'Mercy and compassionate deeds are discussed in this Jewish source.'},
    {id:'unrelated',sourceId:'j2',tradition:'Judaism',text:'Judaism has a long history and many texts.'},
  ]);
  assert.deepEqual(searchIndex(index,next.searchQuestion).map(doc=>doc.id),['mercy']);
});

test('standalone questions, new topics and explicit passages do not inherit prior topics', () => {
  for (const question of [
    'What is mercy?',
    'Why is forgiveness important?',
    'What does Judaism teach about its law?',
    'New topic: what about angels?',
    'Separately, explain this concept of baptism.',
    'Compare interpretations of John 1:1.',
    'What about Romans 9?',
    'Does 1 John 1:1 refer to Jesus?',
  ]) {
    const next=buildConversationContext(question,{history,selectedId:'mercy',context:reading});
    assert.equal(next.followUp,false,question);
    assert.equal(next.searchQuestion,question);
    assert.equal(next.selectionQuestion,question);
    assert.equal(next.context,reading);
    assert.equal(next.parentId,'');
  }
});

test('only the most recent three ancestors are retained, with bounded question text', () => {
  const next=buildConversationContext('Why?',{history,selectedId:'details',context:reading,maxTurns:99});
  assert.deepEqual(next.priorQuestionIds,['judaism','evidence','details']);
  assert.equal(next.priorQuestions.length,3);
  const long=buildConversationContext('Tell me more.',{history:[{id:'long',question:'x'.repeat(5000)}],selectedId:'long'});
  assert.equal(long.priorQuestions[0].length,1200);
});

test('missing selections, cycles and disabled context cannot borrow unrelated history', () => {
  const missing=buildConversationContext('Why?',{history,selectedId:'absent',context:reading});
  assert.equal(missing.followUp,false);
  assert.equal(missing.searchQuestion,'Why?');
  const disabled=buildConversationContext('Why?',{history,selectedId:'mercy',context:reading,maxTurns:0});
  assert.equal(disabled.followUp,false);
  const cycle=buildConversationContext('Why?',{history:[{id:'a',question:'Election?',parentId:'b'},{id:'b',question:'Why?',parentId:'a'}],selectedId:'a'});
  assert.deepEqual(cycle.priorQuestionIds,['b','a']);
});

test('short follow-ups are recognized without treating every question as a continuation', () => {
  for (const question of ['Why?','How so?','What does that mean?','How do they differ?','And the Orthodox view?','Show the sources for that.']) assert.equal(isFollowUp(question),true,question);
  for (const question of ['','Explain mercy.','How did Jesus pray?','What is the history of Jerusalem?']) assert.equal(isFollowUp(question),false,question);
});
