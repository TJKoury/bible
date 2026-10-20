# Custom model experiment: Qwen3 0.6B

Actual training was completed on the local Apple M3 Ultra (60 GPU cores,
256GB unified memory), using Python 3.13.11, MLX-LM 0.32.2 and MLX 0.32.4.
The default experiment is a small, conservative QLoRA adaptation of an
existing instruction model. It is **experimental**, with known citation and
summary errors; it is not a trained theological authority.

## Reproduce

```sh
/opt/homebrew/bin/python3.13 -m venv .cache/venvs/mlx-small
.cache/venvs/mlx-small/bin/python -m pip install -r docs/training-mlx-requirements.txt
python3 scripts/prepare_training.py --equalize-traditions
.cache/venvs/mlx-small/bin/python scripts/train_small_model.py --stage all
.cache/venvs/mlx-small/bin/python scripts/train_small_diagnostics.py
```

`train_small_model.py` defaults to the conservative v2 settings. It verifies
the pinned model and the source/split/text hashes before running, saves every
command and stage log, and skips completed stages of the same experiment.
Use a fresh `--output .cache/training/EXPERIMENT` when changing parameters.
Explicit stages are `download`, `baseline`, `train`, `evaluate`, `export`
and `all`. Training is bounded to at most 1,000 iterations and a 30-minute
subprocess timeout. Nothing is uploaded by these scripts.

The base is
[`mlx-community/Qwen3-0.6B-4bit`](https://huggingface.co/mlx-community/Qwen3-0.6B-4bit),
pinned to `73e3e38d981303bc594367cd910ea6eb48349da8`. Its weight SHA256 is
`392e8d466d56100ada00eb82031fb854297fc9e389b7d303eba3af114e87bce2`.
The weights are **335,450,584 bytes**; the downloaded base package with
tokenizer and license is **351,395,834 bytes**, below 1GB. Its model card
identifies [Qwen/Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B) as the
Apache-2.0 upstream. The conversion's original upstream revision is not
documented by that card; the experiment separately pins the upstream license
file rather than inventing a conversion revision.

Download size is not runtime memory. WebLLM's installed Qwen3-0.6B q4f16_1
configuration estimates approximately **1.4GB GPU memory**, including runtime
overhead. That estimate varies with context and browser.

## Data and experiment

Only the public-domain-in-the-USA historical research corpus was used for
this run. Wikipedia/CC BY-SA encyclopedia text remains a separate export and
was not silently mixed into this model.

Training contains 1,551 passages, with 517 each from Christian, Jewish and
Muslim sources; validation contains 198, with 66 each; test contains 177,
with 59 each. All passages from a source edition stay in one split. Equal
counts do not make the sources representative of all schools, and token
lengths are unequal. Contemporary and non-English voices remain substantial
gaps. Source rights, translations, authors and locators are preserved in
`data-rights-and-splits.json` and `corpus-notices.txt`.

The objective is next-token prediction on historical text. This teaches
language patterns; it does not turn historical assertions into verified
answers, train source ranking, or provide expert labels for theological
disagreement. The evaluation prompts are withheld from training.

| Setting | Conservative v2 |
| --- | --- |
| Iterations | 150 |
| Batch / maximum sequence | 4 / 1,024 tokens |
| Learning rate | 0.000002 |
| LoRA | Rank 8, scale 16, last 8 layers |
| Trainable parameters | 1,441,792 |
| Base quantization | 4-bit, groups of 64 |
| Seed | 17 |
| Observed training time | 93 seconds |
| Tokens processed | Approximately 267,300 |

Long passages were truncated to 1,024 tokens by the loader. Validation runs
used training batch size 4, so two remainder validation records are omitted
by that loader; final held-out test runs use batch size 1 and include all 177
test records. Hyperparameters were revised after an unsuccessful first run;
the reported test/probe set has therefore been inspected during development
and is not an untouched final acceptance benchmark.

## Observed results

| Variant | Held-out loss | Perplexity |
| --- | ---: | ---: |
| Original quantized base | 3.776 | 43.657 |
| v1: aggressive 200-step adapter | 4.585 | 97.989 |
| v2: conservative adapter | 3.580 | 35.868 |
| v2 merged BF16 weights | 3.580 | 35.865 |
| v2 requantized MLX 4-bit weights | 3.764 | 43.113 |

The first run used 28 layers, rank 16 and learning rate 0.00005. It lost
instruction following and produced repetitive, ungrounded answers, so it
was rejected and retained only for audit in `.cache/training/qwen3-0.6b-v1`.

V2 reduced held-out perplexity by about 17.8% **before final requantization**.
This is a language-modeling result, not a theological accuracy improvement.
Requantizing the merged weights back to MLX 4-bit loses much of that gain
(final perplexity is about 1.25% below the original base):

| Held-out source | Base loss | Adapter loss | Requantized MLX loss |
| --- | ---: | ---: | ---: |
| Augustine, *Confessions* — Christianity | 4.126 | 3.922 | 4.114 |
| Maimonides, *Guide* — Judaism | 3.447 | 3.267 | 3.432 |
| al-Ghazali, *Confessions* — Islam | 3.760 | 3.552 | 3.751 |

These each measure one historical source, not the religion as a whole.
MLC browser quantization is a separate conversion and must be checked in the
browser; adapter-only scores must not be presented as browser-model scores.

Seven ad hoc probes compared the base and v2 adapter with identical evidence,
seed and non-thinking sampling settings. V2 preserved the Schreiner/Abasciano
disagreement, distinguished Hagopian's survey from endorsement, and declined
an unsupported excavation quotation. It still misrepresented details of an
Augustine passage, omitted requested exact source IDs in several answers,
and answered an interfaith question too categorically. The Maimonides example
also demonstrates why quoted/criticized arguments need careful role tracking.
The complete prompts and actual outputs are in `answer-probes.json`; final
MLX quantized outputs are in `quantized-answer-probes.json`.

No numerical theological accuracy score is assigned. A deployment should
remain visibly experimental and retain retrieval evidence. Before promoting
these weights, use a new withheld benchmark with qualified review across
the represented traditions, verify citation entailment, and compare final
browser outputs against the original base.

## Local artifacts and browser conversion

`.cache/training/qwen3-0.6b-v2/` contains:

- `run.json`, dependency lock, source rights, notices and all stage logs.
- `adapters/`: final adapter is 5,779,075 bytes, plus saved checkpoints.
- `fused-bf16/`: normal merged weights for conversion, approximately 1.20GB.
  This intermediate exceeds 1GB and is not the browser download.
- `fused-mlx-4bit/`: **346,979,810 bytes** including tokenizer and notices.
- `diagnostics.json`, per-source loss logs, and actual qualitative outputs.

An MLX quantized package cannot be loaded directly by WebLLM. The export
command is:

```sh
python3 scripts/train_export_mlc.py --numpy-quantizer
.cache/venvs/mlx-small/bin/python scripts/train_validate_mlc.py
python3 scripts/train_package.py --format mlx
python3 scripts/train_package.py --format mlc
```

It uses the already installed Docker runtime and a digest-pinned Python
Linux/amd64 image, with an 8GB memory limit and a 15-minute conversion timeout.
Official MLC packages supply the model mapping, weight loader, tensor-cache
writer and Qwen3 configuration with 4,096-token context and 1,024-token prefill.
Only the experiment directory is mounted. Commands, package versions,
input/output hashes and actual success/failure are recorded in
`mlc-export.json` and `mlc-export.log`.

The Linux path was added because native macOS MLC wheels failed during
library initialization. Their signatures were first checked against wheel
RECORD hashes and locally re-signed in the isolated venv; subsequent ABI and
initialization failures remained. No system security setting was changed.
The Linux attempt required `psutil==7.2.2` and `numpy==2.2.6`; the newer NumPy
version rejected a TVM dtype. TVM's CPU quantization JIT then segfaulted.
The successful export used the bounded `--numpy-quantizer` fallback:
`train_mlc_numpy_quant.py` implements the published MLC `q4f16_1` computation
with NumPy, replacing only that JIT calculation. It uses 32-value groups,
FP16 max-absolute/7 scales, rounded/clipped 4-bit values and eight packed
values per uint32. Known-value packing and zero-group fixtures pass. The
official loader/writer converted **113 matrices** and wrote **339 tensors**.
Every tensor name, shape, dtype, codec and byte length matches the official
MLC Qwen3-0.6B q4f16_1 package. Shard lengths, checksums and offsets are checked,
and sampled decoded weights are compared against the merged source.

New TVM writes `tensor-cache.json`; an identical `ndarray-cache.json` is
retained for the installed WebLLM loader. The generated MLC directory is
approximately **347MB** before the small model-card/evaluation attachments.
`CONVERSION-VALIDATION.json` and `QUANTIZATION-PROVENANCE.json` record the
checks and fallback implementation hash. This is a successful weight
conversion, with browser generation still requiring its own verification.

The retained Docker container can be reused on a conversion retry; its name
is recorded in `mlc-export.json`. The packaging script produces release
archives under the experiment's `release/` directory. It includes license,
source rights, model card, actual evaluation outputs and per-file hashes,
and rejects absolute local paths in text metadata. The MLC archive has top
folder `scripture-qwen3-0.6b-v2`; the MLX archive uses
`scripture-qwen3-0.6b-v2-mlx4bit`.

Use a WebLLM model library compatible with the exported architecture and
quantization. The installed WebLLM 0.2.86 package supplies:

```text
https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_86/base/Qwen3-0.6B-q4f16_1_cs1k-webgpu.wasm
```

Preserve the base Apache-2.0 license, model modification notice, corpus
provenance and evaluation limitations with published artifacts. The
Wikipedia export has different terms and would require a separately
documented experiment. Conversion success, browser compatibility and
answer-quality approval are three distinct results.

Implementation references: [MLX-LM LoRA](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/LORA.md),
[MLX fusion](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/fuse.py),
and [MLC custom WebLLM models](https://llm.mlc.ai/docs/deploy/webllm.html).

## Browser verification after packaging

The custom MLC weights loaded successfully in Chrome through WebLLM 0.2.86
and generated a coherent answer about the supplied Genesis 2:1–4 evidence,
with a valid `[S1]` citation. It omitted part of the passage and did not follow
the two-sentence request exactly. This verifies loading and inference, not
theological accuracy or reliable summarization. No browser perplexity score
was measured. The first browser attempt exhausted its output on thinking
tokens; the app now explicitly sends `extra_body.enable_thinking=false`.

WebLLM normalizes model URLs to include a `resolve/REVISION/` component.
The static build therefore hosts this version beneath
`models/scripture-qwen3-0.6b-v2/resolve/v2/`. The installed model library is
reused only after all 339 tensor names/shapes/dtypes were compared with its
official model. The custom weights are a distinct model option from the base.

Release archives were packaged before the browser smoke test and retain that
time's unverified status in their embedded report. This section and
`docs/training-result.json` record the subsequent check. Archive checksums
remain unchanged.
