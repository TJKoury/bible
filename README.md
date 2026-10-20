# Scripture

A Svelte 5 Bible reader with translation comparison, original-language word study,
lemma concordances, and verse cross-references. Vite serves the app; all scripture
data is downloaded and served locally. No Bible API keys are required for the installed editions.

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

## Structure

`src/App.svelte` owns navigation, reader, search, library, and preferences.
`src/lib/StudyPanel.svelte` handles source words and reference exploration.
`src/lib/data.js` contains caching, verse labels, mapping, and concordance access.
`scripts/download_data.py` builds data; `scripts/verify_data.py` checks all concordance
targets, download metadata, archive integrity, and counts.
