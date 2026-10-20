// Browser recognition may use a remote service. The caller must show the
// disclosure and invoke start only after an explicit microphone-button action.
// https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition
export const SPEECH_DISCLOSURE = 'Your browser may send microphone audio to its speech service for transcription. Dictation starts only when you choose Enable dictation; review the text before sending.';

function recognitionClass(scope) {
  const surface = scope.window || scope;
  return surface.SpeechRecognition || surface.webkitSpeechRecognition;
}

export function speechSupport(scope = globalThis) {
  const surface = scope.window || scope;
  const available = typeof recognitionClass(scope) === 'function';
  const secure = surface.isSecureContext !== false;
  return {
    supported: available && secure,
    reason: !secure ? 'Dictation requires HTTPS or localhost.' : !available ? 'Dictation is unavailable in this browser. You can type your question.' : '',
    mayUseRemoteService: true,
  };
}

const errorMessages = {
  'not-allowed': 'Microphone access was denied. You can allow it in browser settings or type your question.',
  'service-not-allowed': 'This browser does not allow its speech service here. You can type your question.',
  'audio-capture': 'No microphone is available. Check your microphone or type your question.',
  network: 'The browser speech service could not connect. You can retry or type your question.',
  'no-speech': 'No speech was detected. Try again when you are ready.',
  'language-not-supported': 'The browser speech service does not support this language.',
  aborted: 'Dictation was stopped.',
};
const emit = (callbacks, name, value) => { if (typeof callbacks[name] === 'function') callbacks[name](value); };
const cleanText = text => String(text || '').replace(/\s+/g, ' ').trim();

function snapshot(results) {
  const final = [], interim = [];
  // Results is the entire current session, not an append-only delta. Interim
  // results can change or disappear; repeated finals must never be duplicated.
  // https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognitionEvent/results
  for (let index = 0; index < (results?.length || 0); index++) {
    const result = results[index];
    const text = cleanText(result?.[0]?.transcript);
    if (text) (result.isFinal ? final : interim).push(text);
  }
  const finalText = final.join(' '), interimText = interim.join(' ');
  return { finalText, interimText, text: [finalText,interimText].filter(Boolean).join(' '), isFinal: !interimText };
}

/** Create without microphone access. Every start creates one isolated session. */
export function createSpeechInput({ lang = 'en-US', scope = globalThis } = {}) {
  const surface = scope.window || scope;
  let state = 'idle', active = null, disposed = false;

  function setState(value, callbacks) {
    state = value;
    emit(callbacks, 'onState', value);
  }
  function finish(session, { cancelled = false, error = null } = {}) {
    if (active !== session) return;
    active = null;
    const { recognition, callbacks, transcript } = session;
    recognition.onstart = recognition.onresult = recognition.onerror = recognition.onend = null;
    // An unfinished hypothesis must not become a committed transcript on end.
    if (!cancelled && transcript.interimText) {
      emit(callbacks, 'onTranscript', { finalText:transcript.finalText, interimText:'', text:transcript.finalText, isFinal:true });
    }
    setState('idle', callbacks);
    emit(callbacks, 'onEnd', { finalText:transcript.finalText, text:transcript.finalText, cancelled, error });
  }
  function fail(session, code) {
    if (active !== session) return;
    const error = { code, message:errorMessages[code] || 'Dictation could not start. You can retry or type your question.' };
    emit(session.callbacks, 'onError', error);
    const recognition = session.recognition;
    finish(session, { error });
    try { recognition.abort(); } catch { /* It may already have stopped. */ }
  }
  function start(callbacks = {}) {
    if (disposed || active) return false;
    const support = speechSupport(scope);
    if (!support.supported) {
      emit(callbacks, 'onError', { code:'unsupported', message:support.reason });
      return false;
    }
    let recognition;
    try {
      const Recognition = recognitionClass(scope);
      recognition = new Recognition();
      recognition.lang = lang;
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
    } catch {
      emit(callbacks, 'onError', { code:'unavailable', message:'Dictation could not start. You can type your question.' });
      return false;
    }
    const session = { recognition, callbacks, transcript:snapshot([]) };
    active = session;
    recognition.onstart = () => { if (active === session && state === 'starting') setState('listening', callbacks); };
    recognition.onresult = event => {
      if (active !== session) return;
      const next = snapshot(event.results);
      const previous = session.transcript;
      session.transcript = next;
      if (next.finalText !== previous.finalText || next.interimText !== previous.interimText) emit(callbacks, 'onTranscript', next);
    };
    recognition.onerror = event => fail(session, event.error || 'unknown');
    recognition.onend = () => finish(session);
    setState('starting', callbacks);
    try { recognition.start(); }
    catch (error) { fail(session, error?.name === 'NotAllowedError' ? 'not-allowed' : 'unavailable'); return false; }
    return true;
  }
  function cancel() {
    if (!active) return false;
    const session = active;
    finish(session, { cancelled:true });
    try { session.recognition.abort(); } catch { /* No active audio is also safe. */ }
    return true;
  }
  function stop() {
    if (!active || state === 'stopping') return false;
    if (state === 'starting') return cancel();
    const session = active;
    setState('stopping', session.callbacks);
    // stop asks the service to finalize captured speech; cancel uses abort.
    // https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition/stop
    try { session.recognition.stop(); }
    catch { cancel(); }
    return true;
  }
  function onHidden() { if (surface.document?.hidden) cancel(); }
  function onPageHide() { cancel(); }
  surface.document?.addEventListener?.('visibilitychange', onHidden);
  surface.addEventListener?.('pagehide', onPageHide);
  function dispose() {
    if (disposed) return;
    const callbacks = active?.callbacks;
    cancel();
    disposed = true;
    state = 'disposed';
    if (callbacks) emit(callbacks, 'onState', state);
    surface.document?.removeEventListener?.('visibilitychange', onHidden);
    surface.removeEventListener?.('pagehide', onPageHide);
  }
  return { start, stop, cancel, dispose, get state() { return state; } };
}
