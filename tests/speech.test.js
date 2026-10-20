import test from 'node:test';
import assert from 'node:assert/strict';
import { createSpeechInput, speechSupport, SPEECH_DISCLOSURE } from '../src/lib/speech.js';

function fixture({ prefixed = false, startError = null } = {}) {
  const instances = [];
  class Recognition {
    constructor() { instances.push(this); this.calls = []; }
    start() { this.calls.push('start'); if (startError) throw startError; }
    stop() { this.calls.push('stop'); }
    abort() { this.calls.push('abort'); }
  }
  const document = new EventTarget();
  document.hidden = false;
  const scope = new EventTarget();
  scope.document = document;
  scope.isSecureContext = true;
  scope[prefixed ? 'webkitSpeechRecognition' : 'SpeechRecognition'] = Recognition;
  const states = [], transcripts = [], errors = [], ends = [];
  const callbacks = {
    onState:state=>states.push(state),
    onTranscript:result=>transcripts.push(result),
    onError:error=>errors.push(error),
    onEnd:result=>ends.push(result),
  };
  const input = createSpeechInput({ scope, lang:'en-GB' });
  return { input, instances, scope, states, transcripts, errors, ends, callbacks };
}
function result(text, isFinal = false) {
  const row = [{ transcript:text }];
  row.isFinal = isFinal;
  return row;
}

test('detection supports standard and prefixed browsers without starting a microphone', () => {
  for (const prefixed of [false,true]) {
    const f=fixture({prefixed});
    assert.equal(speechSupport(f.scope).supported,true);
    assert.equal(f.instances.length,0);
    assert.equal(f.input.state,'idle');
    f.input.dispose();
  }
  assert.equal(speechSupport({}).supported,false);
  assert.equal(speechSupport({SpeechRecognition:class {},isSecureContext:false}).supported,false);
  assert.match(SPEECH_DISCLOSURE,/may send microphone audio/);
});

test('results replace interim hypotheses and do not duplicate repeated final segments', () => {
  const f=fixture();
  assert.equal(f.input.start(f.callbacks),true);
  const recognition=f.instances[0];
  assert.equal(recognition.lang,'en-GB');
  assert.equal(recognition.interimResults,true);
  assert.equal(f.input.start(f.callbacks),false);
  recognition.onstart();
  recognition.onresult({resultIndex:0,results:[result('Compare merry')]});
  recognition.onresult({resultIndex:0,results:[result('Compare mercy',true),result('and juss')]});
  recognition.onresult({resultIndex:1,results:[result('Compare mercy',true),result('and justice',true)]});
  recognition.onresult({resultIndex:1,results:[result('Compare mercy',true),result('and justice',true)]});
  assert.deepEqual(f.states,['starting','listening']);
  assert.equal(f.transcripts.length,3);
  assert.deepEqual(f.transcripts.at(-1),{text:'Compare mercy and justice',finalText:'Compare mercy and justice',interimText:'',isFinal:true});
  f.input.dispose();
});

test('interim removals and a natural end retain only finalized text', () => {
  const f=fixture();
  f.input.start(f.callbacks);
  const recognition=f.instances[0];
  recognition.onstart();
  recognition.onresult({results:[result('Mercy',true),result('uncertain words')]});
  recognition.onresult({results:[result('Mercy',true)]});
  assert.equal(f.transcripts.at(-1).text,'Mercy');
  recognition.onresult({results:[result('Mercy',true),result('another hypothesis')]});
  recognition.onend();
  assert.equal(f.transcripts.at(-1).text,'Mercy');
  assert.equal(f.ends[0].text,'Mercy');
  assert.equal(f.ends[0].cancelled,false);
  assert.equal(f.input.state,'idle');
  assert.deepEqual(recognition.calls,['start']);
  f.input.dispose();
});

test('stop accepts a final result before ending and never restarts automatically', () => {
  const f=fixture();
  f.input.start(f.callbacks);
  const recognition=f.instances[0];
  recognition.onstart();
  assert.equal(f.input.stop(),true);
  assert.equal(f.input.state,'stopping');
  assert.equal(f.input.stop(),false);
  recognition.onresult({results:[result('A final question',true)]});
  recognition.onend();
  assert.deepEqual(recognition.calls,['start','stop']);
  assert.equal(f.ends.length,1);
  assert.equal(f.ends[0].finalText,'A final question');
  assert.equal(f.instances.length,1);
  f.input.dispose();
});

test('cancel detaches handlers and rejects late events from an older session', () => {
  const f=fixture();
  f.input.start(f.callbacks);
  const first=f.instances[0];
  const lateResult=first.onresult, lateEnd=first.onend;
  assert.equal(f.input.cancel(),true);
  assert.equal(first.onresult,null);
  assert.equal(f.ends[0].cancelled,true);
  assert.deepEqual(first.calls,['start','abort']);
  f.input.start(f.callbacks);
  lateResult({results:[result('This must never overwrite the new question',true)]});
  lateEnd();
  assert.equal(f.transcripts.length,0);
  assert.equal(f.ends.length,1);
  assert.equal(f.input.state,'starting');
  f.input.dispose();
});

test('permission errors and thrown starts end safely with actionable errors', () => {
  const denied=fixture();
  denied.input.start(denied.callbacks);
  denied.instances[0].onerror({error:'not-allowed'});
  assert.match(denied.errors[0].message,/Microphone access was denied/);
  assert.equal(denied.input.state,'idle');
  assert.equal(denied.ends.length,1);
  denied.input.dispose();
  const thrown=fixture({startError:Object.assign(new Error('Denied'),{name:'NotAllowedError'})});
  assert.equal(thrown.input.start(thrown.callbacks),false);
  assert.equal(thrown.errors[0].code,'not-allowed');
  assert.equal(thrown.input.state,'idle');
  thrown.input.dispose();
});

test('hidden pages, pending starts and disposal abort capture without late mutations', () => {
  const f=fixture();
  f.input.start(f.callbacks);
  f.input.stop();
  assert.deepEqual(f.instances[0].calls,['start','abort']);
  f.input.start(f.callbacks);
  f.instances[1].onstart();
  f.scope.document.hidden=true;
  f.scope.document.dispatchEvent(new Event('visibilitychange'));
  assert.equal(f.input.state,'idle');
  assert.deepEqual(f.instances[1].calls,['start','abort']);
  f.scope.document.hidden=false;
  f.input.start(f.callbacks);
  const late=f.instances[2].onresult;
  f.input.dispose();
  f.input.dispose();
  assert.equal(f.input.state,'disposed');
  assert.equal(f.input.start(f.callbacks),false);
  late({results:[result('Late text',true)]});
  assert.equal(f.transcripts.length,0);
});
