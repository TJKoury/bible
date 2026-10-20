import { MLCEngine, deleteModelAllInfoInCache, prebuiltAppConfig } from '@mlc-ai/web-llm';
import { models } from './ai.js';
import { assetUrl } from './data.js';
const appConfig = {...prebuiltAppConfig,model_list:[
  ...prebuiltAppConfig.model_list.map(config => {
    const revision = models.find(model => model.id === config.model_id)?.revision;
    return revision ? {...config, model:`${config.model.replace(/\/$/,'')}/resolve/${revision}/`} : config;
  }),
  ...models.filter(m=>m.custom).map(m=>({
    ...prebuiltAppConfig.model_list.find(base=>base.model_id===m.baseId),
    model_id:m.id,
    model:new URL(assetUrl(m.path),self.location.href).href,
  })),
]};
let engine, loadedModelId = '';
self.onmessage = async ({ data }) => {
  try {
    if (data.type === 'load') {
      engine = new MLCEngine({ appConfig, initProgressCallback: progress => self.postMessage({type:'progress',progress}) });
      await engine.reload(data.modelId, {context_window_size:8192,temperature:0.2});
      loadedModelId = data.modelId;
    } else if (data.type === 'generate') {
      if (!engine) throw new Error('Load a model before generating.');
      const options = data.options || {};
      const stream = await engine.chat.completions.create({
        messages:data.messages,stream:true,
        max_tokens:options.max_tokens ?? 1200,temperature:options.temperature ?? 0.2,
        ...(options.top_p !== undefined ? {top_p:options.top_p} : {}),
        ...(options.frequency_penalty !== undefined ? {frequency_penalty:options.frequency_penalty} : {}),
        ...(options.presence_penalty !== undefined ? {presence_penalty:options.presence_penalty} : {}),
        ...(options.response_format ? {response_format:options.response_format} : {}),
        ...(options.seed !== undefined ? {seed:options.seed} : {}),
        ...((models.find(model => model.id === loadedModelId)?.baseId || loadedModelId).startsWith('Qwen3')
          ? {extra_body:{enable_thinking:false}} : {}),
      });
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
