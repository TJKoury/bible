import { MLCEngine, deleteModelAllInfoInCache, prebuiltAppConfig } from '@mlc-ai/web-llm';
import { models } from './ai.js';
import { assetUrl } from './data.js';
const appConfig = {...prebuiltAppConfig,model_list:[
  ...prebuiltAppConfig.model_list,
  ...models.filter(m=>m.custom).map(m=>({
    ...prebuiltAppConfig.model_list.find(base=>base.model_id===m.baseId),
    model_id:m.id,
    model:new URL(assetUrl(m.path),self.location.href).href,
  })),
]};
let engine;
self.onmessage = async ({ data }) => {
  try {
    if (data.type === 'load') {
      engine = new MLCEngine({ appConfig, initProgressCallback: progress => self.postMessage({type:'progress',progress}) });
      await engine.reload(data.modelId, {context_window_size:8192,temperature:0.2});
    } else if (data.type === 'generate') {
      if (!engine) throw new Error('Load a model before generating.');
      const stream = await engine.chat.completions.create({messages:data.messages,stream:true,max_tokens:1200,temperature:0.2,extra_body:{enable_thinking:false}});
      for await (const chunk of stream) {
        const delta = chunk.choices[0]?.delta?.content;
        if (delta) self.postMessage({type:'token',id:data.id,delta});
      }
    } else if (data.type === 'interrupt') {
      await engine?.interruptGenerate();
    } else if (data.type === 'clear') {
      await engine?.unload(); engine = null;
      await deleteModelAllInfoInCache(data.modelId,appConfig);
    }
    self.postMessage({type:'done',id:data.id});
  } catch(e) { self.postMessage({type:'error',id:data.id,message:e.message || String(e)}); }
};
