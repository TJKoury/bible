# Comparative research corpus

The app includes a historical starting collection across Christianity, Judaism and
Islam. No tradition is designated the correct interpretation. Sources retain
named authors, dates, translations, perspectives and locators. Representation is
uneven and incomplete; availability of reusable English texts is a selection bias,
not a measure of religious importance.

The collection contains **13 source editions**, approximately **1.45 million
words**, and **4,465 retrieval passages**. The
generated manifest is the authority for current counts. Public research JSON is
approximately **8.7 MiB**. The already installed Bible editions are separate and
are not duplicated here.

| Tradition | Installed historical sources | Coverage |
| --- | --- | --- |
| Christianity | Augustine, *Confessions*; Aquinas, *Summa* I, Questions 1–26; Luther, *Large Catechism*; Calvin, *Institutes* Volume II; Wesley, *Works* Volume I; Philaret, *Longer Catechism* | Patristic, Roman Catholic/Thomist, Lutheran, Reformed, Wesleyan and Eastern Orthodox texts |
| Judaism | *Pirke Avot* (Gorfinkle); Maimonides, *Guide for the Perplexed* (Friedländer); Kohler, *Jewish Theology* | Rabbinic ethics, medieval Jewish philosophy and a historical Reform presentation |
| Islam | Pickthall's Qur'an translation; al-Ghazali, *Confessions*; Ibn Rushd, *Philosophy and Theology*; Ameer Ali, *Islâm* | Scripture in English translation, Sunni/Sufi, philosophical and modernist/apologetic texts |

These are historical witnesses, not substitutes for contemporary communities.
Anglican, Anabaptist, Pentecostal, Oriental Orthodox and many other Christian
voices remain gaps. Jewish Conservative, Reconstructionist, Hasidic and
contemporary Orthodox traditions are insufficiently covered. Shi'a, Ibadi and
the diversity of contemporary Sunni schools are insufficiently covered.
Ameer Ali's work does not fill those gaps by itself. Original-language theological
sources beyond the Bible, contemporary articles and non-English scholarship need
further acquisition and review.

## Provenance and permissions

The source catalog pages identify the Project Gutenberg editions as public domain
in the USA. The [CCEL source file](https://ccel.org/ccel/s/schaff/creeds2/cache/creeds2.txt)
explicitly identifies its rights as Public Domain. The full Gutenberg license and
per-source credits are retained in
[`public/licenses/research-notices.txt`](../public/licenses/research-notices.txt).
The original editions and download URLs are recorded in the manifest; the exact
download bytes are SHA256-locked. Public-domain status is jurisdiction-specific.
Gutenberg's trademark and redistribution terms remain relevant to reuse of its
branded editions.

No full-text modern Galaxie, JETS, Bible.org or other copyrighted article has been
added to the downloadable corpus. The Romans 9 dossier contains short original
paraphrases and links to the primary arguments. Public access to an article was
not treated as a license to republish or train on it.

The source manifest supplies `author`, `translator`, `tradition`, `perspective`,
`publicationDate`, `sourceUrl`, `downloadUrl`, `license`, `licenseUrl`, `sha256`,
`revision`, `coverageNotes`, `sourceType`, `wordCount`, and `chunkCount`.
Each passage supplies an immutable source-qualified ID, source ID, sequence,
text, heading when recognized, and source-line or Qur'an-verse locator. Source
line references identify the downloaded text file, not a print page number.

The normalization removes ebook header/footer material, collapses line wrapping,
and splits paragraphs into passages. Aquinas includes Questions 1–26; the source
file is downloaded in full to the local cache. Philaret's catechism is extracted
from Schaff's larger collection, leaving Schaff's prefatory evaluation outside
the selection. Some other editions retain translator introductions, editor
notes and quoted opponents; those are not automatically the original author's
assertions.

Only Pickthall's translation is extracted from Gutenberg's three-column Qur'an
edition. All **6,236 verses** in **114 surahs** are validated for unique,
sequential references. Four malformed reference labels in the source are
normalized from their chapter and consecutive context: `0.033` → `17:33`,
`039.04` → `39:46`, `04.032` → `45:32`, and `05.026` → `56:26`. Words are unchanged
apart from whitespace. These corrections are also disclosed in its catalog
entry. An English translation is an interpretation, not the Arabic Qur'an.

## Reproduce downloads

```sh
python3 scripts/download_research.py
```

Raw files are cached in `.cache/research/`; generated public files are:

- `public/data/research/manifest.json`
- `public/data/research/chunks.json`
- `public/data/research/sources.lock.json`
- `public/licenses/research-notices.txt`

An existing lock mismatch fails. Inspect an upstream change before accepting it
with `--refresh`. `dossiers.json` is separately maintained editorial research,
not regenerated from the primary-text corpus.

## Training preparation and actual status

The downloader/exporter prepares data; it does not itself train a model.
An actual **Qwen3-0.6B QLoRA experiment** has now been run on this historical
collection, with preserved base weights, adapters, merged/quantized outputs,
held-out losses and qualitative probes. See
[`docs/training-small-model.md`](training-small-model.md) for reproduction and
the measured limitations. The older 4B recipe below remains an unrun example.
Retrieval context used by the app is still distinct from fine-tuning.

```sh
python3 scripts/prepare_training.py --equalize-traditions
```

This command was run. It creates `.cache/training/research-v1/` with:

- `train.jsonl`, `valid.jsonl`, `test.jsonl`, using plain `{"text": ...}` records.
- A parallel `*.provenance.jsonl` file with source ID, locator and source/text hashes.
- `rights-and-splits.json`, containing licenses, source assignments, checksums,
  selection settings and limitations.

This is **candidate continued-pretraining text**, not supervised answers or
preference labels. No synthetic theological Q&A, modern article full text,
editorial dossier or purported doctrinal consensus is silently made a target.
All passages from each source work remain in the same split, with at least one
held-out document from each religion in validation and test. Deterministic
`--seed` controls assignment. `--equalize-traditions` optionally downsamples to
equal passage counts per religion inside each split; it does not establish
adequate representation within each religion. Shared scriptural quotations and
literary influence can still cross splits despite document separation.

The next training stage requires a selected base model and tokenizer, a measured
baseline, an actual training run, evaluation of attribution and comparison, and
an export compatible with the browser runtime. A training loss or lower
perplexity alone would not demonstrate truthful theological answers. Before
instruction tuning, annotate author assertion versus quoted objection, survey,
editorial comment and response; review that annotation with people familiar with
the traditions being represented. A runtime must also tolerate insufficient
evidence instead of manufacturing a citation.

## Romans 9 research example

`dossiers.json` models the requested claim/evidence/source workflow with an
attribution audit. It separates Schreiner's individual-election argument from
Abasciano's corporate account. Saying that both involve persons is not treated
as agreement on unconditional individual election. Hagopian's introductory
description of his article as a survey is not converted into endorsement of
every view surveyed.

The original journal pagination is recorded: Schreiner 1993, **JETS 36/1,
25–40**; Abasciano 2006, **JETS 49/2, 351–371**; Schreiner's reply, **373–386**.
The dossier links the actual arguments and makes clear that this exchange does
not exhaust Christian interpretation. It does not treat Jewish or Muslim
theology as a response to a Christian doctrinal dispute: related questions are
compared in each tradition's own texts and categories.

The application's answer layer should cite a passage that actually supports
the attributed claim, label its author's perspective, keep objections separate
from conclusions, and state absent coverage. Neither source counts nor a
historical source's polemical language is evidence that one tradition is better
than another.

## Concrete MLX training path on this Mac

The Apple M3 Ultra with 256 GB unified memory is a plausible machine for a
4-billion-parameter LoRA experiment: BF16 weights alone are approximately 8 GB.
That is a capacity estimate, not a measured training-memory or speed result.
Training uses **Metal through MLX**; the resulting inference model later uses
**WebGPU through WebLLM**. The training and browser runtimes are different.
The selected [Qwen3-4B model](https://huggingface.co/Qwen/Qwen3-4B) is a
post-trained chat model under Apache 2.0.

The recipe was checked against **MLX-LM 0.32.2** and its
[LoRA CLI source](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/lora.py).
The [`qwen3` implementation](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/models/qwen3.py)
is present. The wrapper pins the original BF16 model to revision
`1cfa9a7208912126459214e8b04321603b3df60c`, verifies its three weight shards
and tokenizer against provider hashes, and verifies configuration/license
files against their Git object IDs. This avoids assuming an arbitrary local
directory is the intended model.

`scripts/train_model.py` defaults to a dependency-free dry run:

```sh
python3 scripts/prepare_training.py --equalize-traditions
python3 scripts/train_model.py --dry-run
```

The dry run was executed successfully. It validates dataset checksums, rights
metadata, per-record provenance, religion coverage and document separation,
then writes `.cache/training/qwen3-4b-experiment/plan.json`. It does not install
anything, fetch weights or start training.

To execute the experiment later, use native arm64 Python 3.13 or another
supported Python version (MLX-LM 0.32.2 requires Python 3.11+), then run the
following from the project root. The model download is approximately **8.1 GB
of weights**, in addition to tools and intermediate artifacts.

```sh
python3.13 -m venv .cache/venvs/mlx-train
source .cache/venvs/mlx-train/bin/activate
python -m pip install "mlx-lm[train]==0.32.2" huggingface_hub
hf download Qwen/Qwen3-4B \
  --revision 1cfa9a7208912126459214e8b04321603b3df60c \
  --local-dir .cache/models/qwen3-4b
python scripts/train_model.py --train --iters 100
```

The [MLX fine-tuning documentation](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/LORA.md)
supports the `text` JSONL format used here, LoRA, and gradient checkpointing.
The [Hugging Face CLI](https://huggingface.co/docs/huggingface_hub/guides/cli)
supports the pinned revision/local-directory download. No access token is
required for this public base model.

This deliberately small 100-step experiment uses batch size 1, the final 16
layers, maximum sequence length 2,048, and learning rate `1e-5`. These are
starting parameters, not tuned recommendations or a promise of quality.
The wrapper requires a fresh run directory, writes `run.json` and
`training.log`, and records the resulting adapter hash. Use `--output` under
`.cache/` for a separate experiment. It does not overwrite earlier adapters,
upload artifacts, or automatically activate a model in the app.

The plain-text objective is domain adaptation/continued-pretraining-style
training. It does **not** teach a verified citation format or make historical
polemics safe to repeat as neutral conclusions. In particular, adapting a
post-trained chat model on prose may harm instruction-following; measure this
against the untouched model.

For later supervised fine-tuning, build a separate reviewed `messages` dataset
whose target answers correctly identify author, evidence, source locator,
opponent quotation, uncertainty, and disagreement. Include counterexamples
such as Aquinas's objections and Hagopian's survey. Do not mechanically turn a
source passage into a theological “correct answer.” MLX's `--mask-prompt`
applies to chat/completion records, **not** these `text` records.
The current wrapper intentionally accepts only the rights-validated text export;
SFT needs its own reviewed provenance and split manifest.

## Evaluation before using trained weights

Record a baseline before training. The empty adapter path is the documented
MLX mechanism for testing the base model without adapters:

```sh
python -m mlx_lm lora \
  --model .cache/models/qwen3-4b \
  --data .cache/training/research-v1 \
  --test --adapter-path "" --test-batches -1 \
  --max-seq-length 2048

python -m mlx_lm lora \
  --model .cache/models/qwen3-4b \
  --data .cache/training/research-v1 \
  --test --adapter-path .cache/training/qwen3-4b-experiment/adapters \
  --test-batches -1 --max-seq-length 2048
```

These commands report language-model loss/perplexity; they are supported by
the [MLX evaluation implementation](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/lora.py).
They were **not run**, because no base weights or adapters have been installed
for this experiment.

Also maintain a separate, withheld question set reviewed by people familiar
with the represented traditions. Evaluate the base model with retrieval, the
adapter with the same retrieval, and the final quantized browser model under
the same prompts. Report results by tradition and task, including:

- Whether the cited passage entails the attributed claim, rather than merely
  sharing words with it.
- Whether the answer distinguishes an author's conclusion from a survey,
  objection, quotation or editor's note.
- Whether disagreement is accurately preserved without forcing consensus or
  selecting a preferred tradition.
- Whether Jewish and Muslim categories are represented on their own terms,
  with contemporary and underrepresented schools explicitly identified as gaps.
- Whether an unsupported question produces a clear admission of insufficient
  evidence, and whether invented references are absent.
- Whether ordinary reading assistance still works, and whether latency,
  memory use and answer quality remain acceptable after browser quantization.

This is a proposed acceptance process. No human-reviewed benchmark, theological
accuracy score, successful training run or final-model quality result is
claimed.

## Fuse and convert for WebGPU

An MLX adapter is not a WebLLM model. For the BF16 recipe above, first merge the
adapter into normal safetensors:

```sh
python -m mlx_lm fuse \
  --model .cache/models/qwen3-4b \
  --adapter-path .cache/training/qwen3-4b-experiment/adapters \
  --save-path .cache/models/qwen3-4b-research-fused
```

If a separate experiment uses an MLX-quantized base, `mlx_lm fuse --dequantize`
can produce dequantized weights; do not send MLX's quantized tensors directly
to MLC. Retain the exact base-model and adapter relationship. The
[fuse implementation](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/fuse.py)
supports these options. Its GGUF export path does not list Qwen3; this workflow
uses safetensors and does not depend on GGUF.

Use a separate MLC environment. The official
[macOS installation instructions](https://llm.mlc.ai/docs/install/mlc_llm.html)
provide these CPU/Metal packages; nightly package availability changes, so
record the installed versions rather than silently upgrading an existing
toolchain:

```sh
python3.13 -m venv .cache/venvs/mlc-export
source .cache/venvs/mlc-export/bin/activate
python -m pip install --pre -f https://mlc.ai/wheels \
  mlc-llm-nightly-cpu mlc-ai-nightly-cpu
python -m pip freeze > .cache/training/mlc-toolchain.txt
python -c "import mlc_llm, tvm; print(mlc_llm.__file__); print(tvm.__file__)"

python -m mlc_llm convert_weight .cache/models/qwen3-4b-research-fused \
  --quantization q4f16_1 \
  -o .cache/models/qwen3-4b-research-MLC

python -m mlc_llm gen_config .cache/models/qwen3-4b-research-fused \
  --quantization q4f16_1 --conv-template qwen3 \
  --context-window-size 4096 --prefill-chunk-size 1024 \
  -o .cache/models/qwen3-4b-research-MLC
```

The current MLC source contains a dense
[`qwen3` model implementation](https://github.com/mlc-ai/mlc-llm/blob/8978ea9aec626d64096aaa92fbc89bda2e3ea802/python/mlc_llm/model/qwen3/qwen3_model.py),
a [`qwen3` conversation template](https://github.com/mlc-ai/mlc-llm/blob/8978ea9aec626d64096aaa92fbc89bda2e3ea802/python/mlc_llm/conversation_template/qwen3.py),
and the [configuration flags shown above](https://github.com/mlc-ai/mlc-llm/blob/8978ea9aec626d64096aaa92fbc89bda2e3ea802/python/mlc_llm/cli/gen_config.py).
This establishes a supported architecture and command path, not a tested
end-to-end conversion of a trained artifact.

WebLLM also needs a compatible **WebAssembly model library**, not just weight
shards. A LoRA merge that preserves architecture and tokenizer dimensions may
reuse the existing library when quantization and compiler/runtime metadata
match. The installed WebLLM 0.2.86 config currently provides
`Qwen3-4B-q4f16_1-MLC` with a `cs1k` WebGPU library and a 4,096-token context
override. Obtain that library URL from the installed package's
`prebuiltAppConfig`, not from a guessed filename. See the official
[custom-model workflow](https://llm.mlc.ai/docs/deploy/webllm.html).

If a matching library cannot be reused, install the documented MLC source build
and [Wasm environment](https://llm.mlc.ai/docs/install/emcc.html), including TVM
compiler support and `web/prep_emcc_deps.sh`. Then compile:

```sh
python -m mlc_llm compile \
  .cache/models/qwen3-4b-research-MLC/mlc-chat-config.json \
  --device webgpu \
  -o .cache/models/qwen3-4b-research-webgpu.wasm
```

The Wasm setup currently calls out Emscripten **3.1.56** as a workaround for
runtime problems with newer releases. Pin the compiler/source revision and
the WebLLM runtime together. Building only a native Metal library is
insufficient. This build toolchain and export were **not installed or run**.

Publish the converted tokenizer, configuration, shards and matching WASM to
versioned model storage with suitable CORS headers, and add a custom WebLLM
`model_list` entry pointing to those artifacts. Carry forward Apache-2.0 and
corpus provenance in a model card. Do not bundle multi-gigabyte model weights
into this site's static deployment. Finally, test actual WebGPU generation,
citations and memory behavior on the intended browsers before selecting the
custom model in the app. Browser support and `shader-f16` availability still
matter even though training fits on the Mac.

## Separate Wikipedia text export

The encyclopedia can also supply attributed training text. Its license differs
from the historical public-domain collection, so it has a separate export:

```sh
python3 scripts/export_encyclopedia_training.py
```

This reads `public/data/encyclopedia/index.json` and only the retained
`sections[*].text` in the indexed article files. It writes
`.cache/training/encyclopedia-v1/` without changing the encyclopedia or running
training. Article summaries, generated `studyNotes`, editorial `notes`,
bibliography text, external links' contents, modern referenced paper bodies,
images and generated question/answer pairs are excluded. Wikipedia prose can
still contain inline quotations already present in the retained section;
this is not a claim that every sentence was written by Wikipedia editors.

The current export contains **4,456 unique sections, 591,270 words and 792
articles**:

| Split | Unique sections | Words | Articles |
| --- | ---: | ---: | ---: |
| Train | 3,586 | 476,282 | 633 |
| Validation | 466 | 59,603 | 80 |
| Test | 404 | 55,385 | 79 |

Identical sections are deduplicated **before** splitting, comparing Unicode
NFC text with whitespace collapsed. The stored section text is not otherwise
rewritten. Two duplicate occurrences were removed, including one duplicate
group spanning different articles. Every duplicate's attribution remains
attached to the surviving record. Articles sharing a duplicate are joined
into one connected component; the whole component receives one split.
Deterministic seeded component ordering assigns approximately 80/10/10 by
component count. This prevents article and identical-section leakage, but
does not prevent related facts, paraphrases or quotations embedded in larger
sections from appearing across splits.

Each `train.jsonl`, `valid.jsonl` and `test.jsonl` row includes `text` and
attribution metadata: article title, Wikipedia contributors, pinned revision
URL, contributor-history URL, license link, original import modification
notice, section locator, truncation status and SHA256 hashes of the text,
stored article file and available upstream response. Matching
`*.provenance.jsonl` sidecars retain the metadata separately.
`rights-and-splits.json` records input hashes, article/component assignments,
output hashes, counts, exclusions and limitations. `ATTRIBUTION.md` explains
the transformation and reuse terms. Export artifacts total approximately
19.6 MiB because attribution is present both in each record and in sidecars;
they remain outside the public site bundle.

This retained/adapted text dataset is distributed under **CC BY-SA 4.0**.
Keep its credit, license, history/revision links and modification notices with
redistributed copies; share adapted text under the applicable ShareAlike
terms. See the [CC BY-SA 4.0 legal code](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en)
and [Wikimedia's content reuse terms](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content).
Neither Wikimedia nor its contributors endorse this project.

The public-domain MLX wrapper intentionally does **not** accept this export.
Do not combine it silently with `research-v1`, relabel it public domain, or
assume Qwen's Apache-2.0 license resolves the distribution terms of weights
trained on it. A future encyclopedia training experiment needs its own
recorded data/license review and model card, including a review of obligations
for publishing the resulting weights and generated reproductions.

Validation compared every exported text and attribution to its source
section, recomputed file/text hashes, checked all 792 article assignments and
confirmed no normalized-section or article overlap between splits. A small
fixture also checked transitive cross-article duplicate grouping. This is
data-integrity verification, not evaluation of theological accuracy. The
encyclopedia is mostly geographic secondary reference material and is not a
balanced representation of religious traditions. No custom model was trained
from this export.
