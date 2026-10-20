// A small worker client keeps the GPU runtime out of the main UI bundle.
export class LocalModel {
  constructor(onProgress = () => {}) {
    this.pending = new Map(); this.sequence = 0;
    this.worker = new Worker(new URL('./model.worker.js', import.meta.url), {type:'module'});
    this.worker.onmessage = ({data}) => {
      if (data.type === 'progress') { onProgress(data.progress); return; }
      const pending = this.pending.get(data.id);
      if (!pending) return;
      if (data.type === 'token') { pending.onToken?.(data.delta); return; }
      this.pending.delete(data.id);
      if (data.type === 'error') pending.reject(new Error(data.message));
      else pending.resolve();
    };
    this.worker.onerror = () => this.fail(new Error('The WebGPU model worker stopped. Unload and reload the model to retry.'));
  }
  send(type, data = {}, onToken) {
    const id = ++this.sequence;
    return new Promise((resolve,reject) => {
      this.pending.set(id,{resolve,reject,onToken});
      this.worker.postMessage({type,id,...data});
    });
  }
  load(modelId) { return this.send('load',{modelId}); }
  generate(messages,onToken) { return this.send('generate',{messages},onToken); }
  interrupt() { return this.send('interrupt'); }
  clear(modelId) { return this.send('clear',{modelId}); }
  fail(error) { for (const pending of this.pending.values()) pending.reject(error); this.pending.clear(); }
  dispose() { this.worker.terminate(); this.fail(new Error('Model session closed.')); }
}
