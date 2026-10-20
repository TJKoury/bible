# Local AI quality diagnosis

Recorded 20 October 2026. Bible AI now uses constrained source selection and displays original indexed passages instead of model-written theological paraphrases. The original custom Qwen3 0.6B model was unreliable for free-form, citation-grounded comparison. Those attribution failures also occur in the final native MLX 4-bit model: MLC conversion is not required to reproduce them. Short prompts improve brevity but do not fix the underlying errors.

[The diagnostic record](local-ai-diagnostics.json) preserves the exact native fixtures and messages, all **20 native outputs**, **five custom WebGPU outputs**, and **five base WebGPU outputs**. It also preserves five initial, misconfigured Qwen2.5 outputs and a later intermediate selection run. The [final browser evaluation](local-ai-browser-evaluation.json) retains five actual requests and raw outputs for the corrected selection path. These are inspected development cases, not an untouched expert-reviewed benchmark or a theological accuracy score.

## What was tested

The five cases cover John 1:1–4; mercy in named passages by Calvin, Kohler and Ameer Ali; Schreiner versus Abasciano with Hagopian as a survey; an absent 2025 excavation quotation; and interpretation of election “in Christ.” The Romans fixture uses editorial summaries, explicitly labeled as such, rather than pretending they are quotations from the scholars.

Native testing compared the base and custom final MLX 4-bit weights, each with the then-current application prompt and a concise evidence prompt. It used temperature 0.2, top-p 1, seed 41, non-thinking mode and a 320-token output cap. Native prompts contained 159–1,731 tokens, below the application's requested 8,192-token context. Repetition and false attribution therefore cannot be explained solely by context-window overflow. Outputs that reach the cap may be incomplete; the original application allowed 1,200 output tokens.

Browser testing used the same five questions and evidence packets, but a different brief prompt and temperature 0.7, top-p 0.8, presence penalty 0.5, seed 41 and a 380-token cap. Both Qwen3 runs used `enable_thinking=false` and `/no_think`. This demonstrates failure in both runtimes; it is not a controlled numerical comparison between MLX and MLC.

Tests ran on a Mac Studio with an Apple M3 Ultra, 60 GPU cores, 256 GB unified memory and macOS 26.3.1 (a). Native packages were MLX 0.32.4, MLX-LM 0.32.2 and Transformers 5.20.2; the browser used WebLLM 0.2.86.

| Case | Observed failure or success |
| --- | --- |
| John | Native models change “in the beginning” into a claim that the Word is the beginning of all things. Custom WebGPU invents an additional `[1]` citation and fails to identify the book clearly. |
| Mercy | Native outputs mistake source footnotes for answer citations and introduce unsupported qualifications. Browser base misattributes an opponent's position to Kohler; browser custom gives generic commentary instead of comparing the views. |
| Romans | The custom native concise answer blurs the authors' disagreement. Longer native and both original browser runs reverse Schreiner's position; custom WebGPU also assigns Abasciano's argument to Hagopian. |
| Missing excavation | Both models abstain in both runtimes. |
| Ephesians | Native outputs introduce unsupported distinctions or wording. Both original browser outputs present a corporate conclusion as settled by the excerpt. |

## Training and artifact audit

The [v2 training record](training-result.json) describes continued-text QLoRA on 1,551 historical prose passages from 13 works, with 517 training passages per religion. Plain `text` records and `mask_prompt:false` train continuation, not supervised theological Q&A. There are no labeled citation, author-role or evidence-selection targets. Equal passage counts also do not establish equal token counts or coverage of internal traditions.

The run used 150 iterations, batch 4, a 1,024-token limit, learning rate 0.000002 and rank-8 adapters in eight layers, processing approximately 267,300 tokens. Held-out prose perplexity was 43.657 for the base, 35.868 with the adapter and 43.113 after final MLX 4-bit requantization. Most of the measured improvement disappears in the final MLX artifact. Perplexity is a next-token measure, not evidence of trustworthy answers; the browser artifact has no corresponding measured perplexity.

The base and merged BF16 SHA-256 checks match the recorded provenance. All nine MLC shard sizes and MD5 checks pass, totaling 335,372,288 bytes. Existing conversion checks validate the tensor schema and sampled quantization error. Despite different tokenizer JSON flags, all ten diagnostic prompt strings produce identical token IDs and decoded text with both tokenizers. These checks establish artifact consistency, not semantic accuracy.

Quantization may contribute to differences: the custom MLC artifact is derived from an already quantized base, merged and quantized again with a different scheme. It is not a sufficient explanation for failures that already occur in native MLX. Earlier successful development probes do not override the failures preserved here.

## Implemented correction and its limits

The application asks the model to select supplied passage IDs through a constrained JSON schema. [`grounding.js`](../src/lib/grounding.js) creates bounded extracts from indexed source text, retains their source metadata and offsets, validates the returned IDs, and renders the corresponding extracts. Raw model prose is not displayed as an answer. Invalid or empty selections produce an explicit message and leave the retrieved references available for inspection.

Packets contain at most 20 choices from eight sources, with up to 1,200 characters per extract and 14,000 characters across extracts. The larger extract allowance retains a long Ameer Ali sentence that the earlier 650-character limit omitted. These limits and the choice ranking still exclude some material; the model only sees the supplied packet.

Source packets preserve editorial-summary labels and available author-role warnings. Each question retains its own reading context, evidence and selected passages in the Bible AI timeline. Typing or optional browser dictation supplies the question; neither input method changes the grounding checks. Dictation may use a browser-provider service and is separate from local model inference.

**Exact quotation and source-ID validation does not establish semantic entailment.** It also does not establish relevance, speaker endorsement, complete context, representative religious coverage or theological truth. A faithful quotation may still be irrelevant, an opponent's words, or misleading without surrounding context. Selected evidence must remain visibly distinct from a complete theological answer.

No retraining was performed during this diagnosis. Any future training should supervise the actual tasks—source selection, attribution, survey versus endorsement and abstention—and evaluate a withheld source/question-family split on the final quantized browser artifact.

## Corrected WebGPU results

The [recorded browser run](local-ai-browser-evaluation.json) used the pinned Qwen2.5 model with WebLLM 0.2.86 in Chrome WebGPU, temperature 0.2, top-p 0.8, seed 41, a 160-token cap and a constrained selection schema. All five responses were valid JSON containing only known choice IDs. That is a format result, not five fully correct answers.

| Case | Actual result and remaining limit |
| --- | --- |
| John | Selects the complete supplied John 1:1–4 passage. Displayed wording and book attribution come from the source record. |
| Mercy | Selects relevant Calvin, Kohler and Ameer Ali passages, including the long Ali passage about divine mercy. The raw selection also contains redundant neighboring windows. |
| Romans | Selects the editorial summaries preserving Schreiner's and Abasciano's different positions. It omits Hagopian's supplied survey summary, leaving that part of the question unanswered. |
| Missing excavation | Returns an empty selection for the absent 2025 quotation. |
| Ephesians | Selects biblical wording, without generating an exclusive corporate or individual doctrinal conclusion. The raw selection repeats overlapping windows. |

After that model run, deterministic overlap filtering was added to the validator. A Node replay rebuilt each packet from the saved fixtures, verified that it exactly matched the browser's recorded user packet, and validated the original raw output. Mercy's six selected windows became four; Ephesians' six became three. Other selections were unchanged. The JSON retains the original `validated` values alongside `postprocessedValidation` and identifies the replay's code and fixture hashes. **This was a postprocessing replay, not another browser model run.** It does not fill the omitted Hagopian source or establish semantic relevance.

The earlier corrected-runtime selection attempt is preserved separately in the diagnostic record. It returned false empty selections for Romans and Ephesians, and its Ali extract did not contain the longer divine-mercy passage. The prompt and extraction limits were revised using those results. This development process and the missed source in the final run are reasons to retain the limitations, not claim theological correctness or religious neutrality.

## Conversation and interface check

The production bundle was also exercised beneath `/bible/` with the full local corpus. A Romans 9 comparison returned the biblical passage and labeled summaries of Abasciano and Schreiner. A follow-up, “What about Hagopian?”, retained that conversation branch and put Hagopian’s survey first in the references after a current-question reranking fix. The small model nevertheless returned an empty selection for that follow-up. The interface reported the abstention and kept the relevant reference available; contextual retrieval is working, but conversational selection remains incomplete. Prior AI output is never used as evidence.

Desktop, tablet, and mobile checks confirmed aligned chat/reference widths, independent scrolling, an empty initial question history, and a separate rounded composer. Citation buttons focused the corresponding reference without scrolling the document. Dictation disclosure and cancellation were checked without recording microphone audio; mocked recognition tests cover interim/final results, denied permissions, cancellation, stale events, and page visibility. Live speech transcription quality was not tested.

## Default model provenance

The official [MLC Qwen2.5 1.5B instruction package](https://huggingface.co/mlc-ai/Qwen2.5-1.5B-Instruct-q4f16_1-MLC/tree/9bd564b064631febf14deadcac492efb761d60c3), pinned at `9bd564b064631febf14deadcac492efb761d60c3`, contains **880,289,238 bytes** across 39 files, including **868,547,584 weight-shard bytes**. The exact total is the sum of file sizes in the [official pinned metadata](https://huggingface.co/api/models/mlc-ai/Qwen2.5-1.5B-Instruct-q4f16_1-MLC/revision/9bd564b064631febf14deadcac492efb761d60c3?blobs=true); the diagnostic JSON preserves the file list and checksums.

This repository total excludes the separately hosted compiled WASM and JavaScript runtime. Download size is also distinct from runtime memory: installed WebLLM estimates 1,629.75 MB at a 4,096-token context. The [upstream license is Apache 2.0](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/blob/989aa7980e4cf806f80c7fef2b1adb7bc71aa306/LICENSE); its pinned revision and license SHA-256 are preserved in the diagnostic record.

Qwen2.5 1.5B is the default instruction model for the constrained selection task; the historical Qwen3 adaptation remains experimental. Initial Qwen2.5 browser testing erroneously inherited Qwen3-specific thinking settings. The worker now applies that override only to Qwen3. The initial outputs are retained as an explicitly excluded run, not acceptance evidence for the corrected configuration. The corrected results above establish that this bounded path runs and preserves displayed source wording; they do not certify complete answers or reliable theological judgments.
