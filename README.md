# Scripture

A Svelte 5 Bible reader with translation comparison, original-language word study,
lemma concordances, and verse cross-references. Vite serves the app; all scripture
data is downloaded and served locally. No Bible API keys are required for the installed editions.
It also includes an attributed study encyclopedia, passage-linked 2D/3D geography,
and a local research desk comparing Christian traditions, Judaism, and Islam.

## Run

Requires Node 22.12+ (or a supported newer release) and Python 3.10+ for data tools.

```sh
npm install
npm run dev
```

Open http://127.0.0.1:4173/. The dev server uses a strict port.

```sh
npm run check
npm test
npm run verify:data
npm run build
```

## Features

- Book, chapter, and verse navigation with URL history and the last reading position.
- 14 downloaded English editions: BSB, WEB, KJV, ASV, BBE, Darby, YLT, DRC, Webster,
  JPS 1917, Rotherham, Geneva 1599, NHEB, and CPDV.
- Whole-source JSON downloads in ZIP archives. DRC and CPDV include 73 books; JPS contains the Tanakh.
- WLC Hebrew/Aramaic and SBLGNT Greek with MACULA lemmas, morphology, contextual
  glosses, and Strong’s identifiers. Hebrew tokens include morphemes and affixes.
- Full-corpus lemma concordances, with English passage previews.
- 344,799 ranked OpenBible cross-reference links, preserving verse ranges.
- English-to-Hebrew verse mapping, including different Psalm-heading numbering.
- Full-text search within the selected translation, reference search, translation
  comparison, bookmarks, reading size, evening theme, and focus mode.
- Small-screen layout with a dismissible verse-study panel.
- A visible light/dark switch, with the choice saved in this browser.
- 792 abridged Wikipedia articles about places, people, objects, and other subjects,
  with source revisions, contributor history, and separately grouped archaeology,
  artifacts, maps, literature, and references. Bethsaida has sourced study notes
  comparing the et-Tell and el-Araj excavation projects.
- 1,342 biblical places with 4,370 candidate identifications, linked to 5,616 verses
  across 860 chapters. MapLibre renders 2D maps and actual 3D elevation, preserving
  uncertain and alternative locations. Empty passages remain empty.
- Local passage retrieval across 13 theological works (4,465 passages, about 1.45
  million words), BSB, and encyclopedia summaries; relevant encyclopedia sections
  load on demand. Faith labels identify sources without choosing a preferred faith.
- Optional Qwen3 8B, 4B, 1.7B, or 0.6B inference on WebGPU. Download progress,
  cancellation, unload, cache removal, streaming answers, source selection, citation
  links, and Markdown/copy exports are included. No hosted model API receives questions.
- A source-linked Romans 9 comparison keeps Schreiner, Abasciano, and Hagopian
  distinct and corrects endorsement/pagination overstatements in the example answer.

## Study data and local AI

```sh
npm run data:geography       # reuse pinned source revisions and cache
npm run data:research        # reuse locked historical texts
npm run verify:study
npm run training:prepare    # export equal passage counts per religion, source-disjoint splits
npm run training:encyclopedia # separate attributed Wikipedia section export
npm run training:plan       # validate data and write a dry-run plan; no model training
```

`scripts/download_geography.py --refresh` deliberately refreshes Wikipedia revisions.
The encyclopedia importer retains bibliographic pointers, not the full text of every
paper referenced by Wikipedia. Text is abridged and section grouping is automatic.
See `public/data/encyclopedia/index.json` for coverage, omitted disambiguation pages,
and source attribution. Modern archaeological findings in the Bethsaida notes are
attributed to the excavation teams, not presented as independently adjudicated facts.

Research text/source metadata and hashes are in `public/data/research/`.
[Research data and training documentation](docs/research-data.md) describes each
source, tradition, rights, gaps, the training split, and the complete MLX → MLC →
WebGPU conversion path. `scripts/train_model.py --train` runs an explicit local
LoRA experiment only after the documented dependencies and checksum-pinned base
weights are installed. Its default dry run does not download weights or train.
The separate encyclopedia export contains 4,456 retained sections (591,270 words),
with article-separated splits, revision links, attribution, and CC BY-SA notices.
It excludes generated notes and the bodies of papers linked from Wikipedia.

**No custom theological model has been trained or deployed.** The app currently
uses a pretrained model with retrieved evidence. Raw historical texts are not a
reviewed question/answer dataset. An experiment on those texts would be domain
adaptation, not proof of accurate theology or reliable citation. Quality evaluation
needs held-out questions and attribution checks across the represented traditions,
including distinctions between an author's argument, an objection, and a survey.

Load a model from **Research desk → Load local model**. A secure context (localhost
or HTTPS), WebGPU, and `shader-f16` support are required. Qwen3 8B needs roughly a
4.7 GB initial weight download and 6+ GB of available GPU memory; 4B downloads
about 2.4 GB. Smaller
models use less memory but have weaker reasoning. Models are downloaded from
Hugging Face and a WebGPU runtime from MLC's GitHub repository; browser caching is
best-effort. Sources can still be searched and exported without a model.

The app checks whether generated citation IDs exist in the selected evidence
packet. It **does not automatically verify entailment or author endorsement**.
Those checks remain visible review questions. Retrieval uses BM25 and source
diversity rather than a semantic embedding model, so ambiguous vocabulary can
produce irrelevant matches. Users can inspect and change the evidence packet.

Map tiles load online from OpenStreetMap and elevation from Mapterhorn; no tiles
are bulk downloaded. Set `VITE_MAP_TILES` to a compatible raster endpoint to use
another provider, and update attribution for that provider. Maps show modern
terrain/shorelines with 1.4× elevation in 3D, not an ancient reconstruction.
Regions may be represented by a reference point. OpenBible source rankings are
historical aggregates, not current probabilities.

## Data and provenance

`public/data/catalog.json` describes installed translations and source gaps.
`public/data/sources.json` records source URLs, byte counts, and SHA-256 hashes.
`sources.lock.json` pins repository revisions. Complete original downloads stay in
the ignored `.cache/` directory. Refresh the derived library with:

```sh
npm run data
```

The downloader uses Python’s standard library and reuses cached files. To deliberately
update a source, remove its cache entries and its revision in `sources.lock.json`,
then regenerate and re-run validation. Never substitute another edition to fill gaps.

Data comes from:

- [Scrollmapper](https://github.com/scrollmapper/bible_databases): English editions,
  with individual edition notices and repository MIT license.
- [Thiago Bodruk’s Bible repository](https://github.com/thiagobodruk/bible): KJV text.
- [TehShrike’s World English Bible](https://github.com/TehShrike/world-english-bible):
  WEB text, including paragraph and poetic line segments.
- [MACULA Hebrew](https://github.com/Clear-Bible/macula-hebrew) and
  [MACULA Greek](https://github.com/Clear-Bible/macula-greek): CC BY 4.0 linguistic
  annotations. Required underlying credits are in `public/licenses/` and the Sources dialog.
- [OpenBible.info](https://www.openbible.info/labs/cross-references/): CC BY references.
- [SIL libpalaso](https://github.com/sillsdev/libpalaso): verse-number mappings.

The app’s code license does not override these data licenses. KJV Crown rights apply
in the UK. Original-language ZIP downloads include attribution and modification notices.

## Current limits

- NIV, ESV, NLT, NASB, NKJV, CSB, NRSVue, and NET are **not downloaded**. The library
  links to publisher information. A suitable license or authorized provider is needed
  before adding them. No licensed-provider integration has been implemented.
- English scope is the default. Hebrew/Aramaic and Greek are study datasets, not
  selectable reading translations. Septuagint, Latin, other world languages, and
  original texts for deuterocanonical books are not installed.
- Some upstream text exports have empty verses caused by omissions, numbering, or
  extraction gaps. These are exposed in the UI and download metadata, never silently
  filled with another translation. Entirely empty books/chapters are excluded.
- Automatic study alignment and comparison are disabled for JPS, DRC, and CPDV,
  which use native numbering. Their texts remain readable and downloadable.
- Whole-verse English/Hebrew mappings are applied. Split-verse distinctions and
  textual variants are not an exhaustive critical apparatus. English words are
  not individually aligned to source-language tokens.
- Glosses are contextual aids, not a comprehensive dictionary. Shared lemmas do
  not imply identical meaning. Cross-reference previews show the first verse of a range.
- Bookmarks and preferences are browser-local. Downloads save data files; this is
  not yet an installable offline PWA.
- The encyclopedia, archaeological catalog, and theological library are broad
  starting collections, **not exhaustive**. Missing artifact or literature sections
  are disclosed. Historical availability and public-domain status do not make a
  source authoritative or representative of a whole religion.
- Internal diversity and contemporary scholarship remain unevenly covered.
  Christian, Jewish, and Muslim categories are not treated as interchangeable.
- Exact passage geography uses English numbering for the 66-book corpus. It is
  disabled for native-numbered editions; the standalone atlas remains searchable.
- The browser runtime and map library are loaded separately from the reader.
  Initial model downloads and GPU compilation can take time; this is not a
  model-training runtime in the browser.

## Structure

`src/App.svelte` owns navigation, reader, search, library, and preferences.
`src/lib/StudyPanel.svelte` handles source words and reference exploration.
`src/lib/data.js` contains caching, verse labels, mapping, and concordance access.
`scripts/download_data.py` builds data; `scripts/verify_data.py` checks all concordance
targets, download metadata, archive integrity, and counts.
`Atlas.svelte`, `MapView.svelte`, and `Encyclopedia.svelte` handle study context.
`Research.svelte` and two dedicated workers isolate retrieval and model inference
from the reading UI. `retrieval.js` handles ranking, source diversity and citation
identifier checks; `ai.js` defines the comparative research prompt.
