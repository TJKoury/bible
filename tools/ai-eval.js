import { LocalModel } from '../src/lib/model.js';
import { models, buildMessages } from '../src/lib/ai.js';
import { inspectDevice, modelCompatibility } from '../src/lib/device.js';
const $ = id => document.getElementById(id);
const groundingPath = '/src/lib/grounding.js';
const device = await inspectDevice();
$('device').textContent = JSON.stringify(device, null, 2);
for (const model of models) {
  const option = new Option(model.title, model.id);
  option.disabled = !modelCompatibility(model, device).allowed;
  $('model').add(option);
}
let engine, loadedModelId = '', stop = false;
const status = text => $('status').textContent = text;
$('load').onclick = async () => {
  $('load').disabled = true; $('run').disabled = true;
  engine?.dispose();
  engine = new LocalModel(progress => status(progress.text));
  const modelId = $('model').value;
  try { await engine.load(modelId); loadedModelId = modelId; status(`Model loaded: ${modelId}`); $('run').disabled = false; }
  catch (error) { status(error.message); }
  finally { $('load').disabled = false; }
};
$('stop').onclick = () => { stop = true; engine?.interrupt(); };
$('model').onchange = () => { $('run').disabled = $('model').value !== loadedModelId; };
$('run').onclick = async () => {
  $('load').disabled = true; $('run').disabled = true; $('stop').disabled = false; stop = false;
  $('model').disabled = true; $('prompt').disabled = true;
  $('results').replaceChildren();
  try {
    const fixtures = await fetch('./ai-eval-fixtures.json').then(response => response.json());
    for (const fixture of fixtures) {
      if (stop) break;
      const article = document.createElement('article');
      const title = document.createElement('h2');
      title.textContent = fixture.id;
      const prompt = document.createElement('pre');
      prompt.textContent = fixture.question;
      const output = document.createElement('pre'); output.className = 'answer';
      article.append(title, prompt, output); $('results').append(article);
      const mode = $('prompt').value;
      let messages, options = {max_tokens:380, temperature:0.7, top_p:0.8, presence_penalty:0.5, seed:41};
      if (mode === 'current') messages = buildMessages(fixture.question, fixture.evidence);
      else if (mode === 'brief') messages = [
        {role:'system',content:'Answer the question in at most three sentences using only the evidence. Cite each statement with its exact source ID. An author is not a whole tradition. Do not confuse a quoted opponent with the author. Say when the evidence cannot answer.'},
        {role:'user',content:`Evidence:\n${fixture.evidence.map(e=>`${e.citation} ${e.title} — ${e.author || ''}\n${e.excerpt}`).join('\n\n')}\n\nQuestion: ${fixture.question}\nAnswer briefly with source IDs.`},
      ];
      else {
        const grounding = await import(/* @vite-ignore */ groundingPath);
        const choices = grounding.buildEvidenceChoices(fixture.question,fixture.evidence);
        messages = grounding.buildSelectionMessages(fixture.question,choices);
        options = {max_tokens:160,temperature:0.2,top_p:0.8,seed:41,response_format:grounding.selectionResponseFormat(choices)};
      }
      status(`Running ${fixture.id}…`);
      const request = document.createElement('details');
      const summary = document.createElement('summary'); summary.textContent = 'Exact request';
      const requestBody = document.createElement('pre'); requestBody.className = 'request';
      requestBody.textContent = JSON.stringify({modelId:loadedModelId,mode,messages,options},null,2);
      request.append(summary,requestBody); article.append(request);
      const start = performance.now();
      await engine.generate(messages, delta => output.textContent += delta, options);
      article.dataset.seconds = String(Math.round((performance.now()-start)/100)/10);
      if (mode === 'grounded') {
        const grounding = await import(/* @vite-ignore */ groundingPath);
        const choices = grounding.buildEvidenceChoices(fixture.question,fixture.evidence);
        const result = grounding.validateSelection(output.textContent,choices);
        const checked = document.createElement('pre');
        checked.className='validated';
        checked.textContent=JSON.stringify(result,null,2);
        article.append(checked);
      }
    }
    status(stop ? 'Stopped.' : 'Evaluation complete.');
  } catch(error) { status(error.stack || error.message); }
  finally { $('load').disabled=false; $('run').disabled=false; $('stop').disabled=true; $('model').disabled=false; $('prompt').disabled=false; }
};
