#!/usr/bin/env python3
"""Export attributed Wikipedia prose with article-disjoint, deduplicated splits.

Standard library only. Reads the existing encyclopedia without changing it.
Does not train a model or include study notes, bibliography bodies or Q&A.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import unicodedata
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LICENSE = "CC BY-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
SPLITS = ("train", "valid", "test")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical_text(text):
    """Only used for duplicate detection; the exported prose is unchanged."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def dump_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def validate_source(article, entry):
    for key in ("id", "title", "revision", "revisionUrl", "historyUrl",
                "license", "licenseUrl"):
        if not article.get(key) or article[key] != entry.get(key):
            raise ValueError(f"Missing or inconsistent {key}: {entry.get('id')}")
    if article["license"] != LICENSE or article["licenseUrl"] != LICENSE_URL:
        raise ValueError(f"Unexpected license: {article['id']}")
    revision = urlsplit(article["revisionUrl"])
    history = urlsplit(article["historyUrl"])
    if (revision.scheme != "https" or revision.netloc != "en.wikipedia.org"
            or parse_qs(revision.query).get("oldid") != [str(article["revision"])]
            or history.scheme != "https" or history.netloc != "en.wikipedia.org"
            or parse_qs(history.query).get("action") != ["history"]
            or article.get("attribution") != "Wikipedia contributors"):
        raise ValueError(f"Invalid revision/history/attribution: {article['id']}")


def load_sections(index_path):
    raw_index = index_path.read_bytes()
    index = json.loads(raw_index)
    if index["meta"]["articleCount"] != len(index["articles"]):
        raise ValueError("Index article count does not match its entries")
    root = (ROOT / "public/data/encyclopedia/articles").resolve()
    sources, groups = {}, {}
    empty_sections = 0
    for entry in sorted(index["articles"], key=lambda item: item["id"]):
        article_path = (ROOT / "public" / entry["path"].lstrip("/")).resolve()
        if article_path.parent != root or article_path.suffix != ".json":
            raise ValueError(f"Article path is outside the encyclopedia: {article_path}")
        raw_article = article_path.read_bytes()
        article = json.loads(raw_article)
        validate_source(article, entry)
        sid = article["id"]
        if sid in sources:
            raise ValueError(f"Duplicate article id: {sid}")
        source = {key: article[key] for key in (
            "id", "title", "url", "revision", "revisionUrl", "historyUrl",
            "license", "licenseUrl", "attribution", "retrievedAt",
            "abridged", "modifications", "category")}
        source.update(
            path=entry["path"], articleFileSha256=sha256(raw_article),
            upstreamResponseSha256=article.get("source", {}).get("sha256"),
            retainedSectionCount=0,
        )
        sources[sid] = source
        # Deliberate field allowlist: no summaries, studyNotes, notes, references,
        # externalReferences, linked pages or generated theological answers.
        for ordinal, section in enumerate(article["sections"]):
            text = section.get("text")
            if not isinstance(text, str):
                raise ValueError(f"Non-text section: {sid}:{ordinal}")
            canonical = canonical_text(text)
            if not canonical:
                empty_sections += 1
                continue
            digest = sha256(canonical.encode("utf-8"))
            provenance = {
                **source,
                "sectionOrdinal": ordinal,
                "sectionTitle": section["title"],
                "sectionAnchor": section.get("anchor", ""),
                "sectionUrl": section["url"],
                "sectionCategory": section.get("category", "unclassified"),
                "sectionTruncated": section.get("truncated", False),
                "citationIds": section.get("citationIds", []),
                "textSha256": sha256(text.encode("utf-8")),
            }
            provenance.pop("retainedSectionCount")
            if section["url"].split("#")[0] != article["revisionUrl"]:
                raise ValueError(f"Section does not link to pinned revision: {sid}:{ordinal}")
            if digest not in groups:
                groups[digest] = {
                    "id": f"wikipedia-section:{digest}", "text": text,
                    "normalizedTextSha256": digest, "sources": [],
                }
            elif canonical_text(groups[digest]["text"]) != canonical:
                raise ValueError("Unexpected text hash collision")
            groups[digest]["sources"].append(provenance)
            source["retainedSectionCount"] += 1
    return sources, groups, {
        "indexSha256": sha256(raw_index),
        "indexGeneratedAt": index["meta"].get("generatedAt"),
        "inputArticles": len(sources),
        "inputNonemptySections": sum(s["retainedSectionCount"] for s in sources.values()),
        "emptySectionsSkipped": empty_sections,
    }


def assign_splits(sources, groups, seed):
    # A cross-article duplicate creates a shared component. Keeping the entire
    # component together preserves article separation even after deduplication.
    parent = {sid: sid for sid in sources}

    def find(sid):
        while parent[sid] != sid:
            parent[sid] = parent[parent[sid]]
            sid = parent[sid]
        return sid

    for group in groups.values():
        first = group["sources"][0]["id"]
        for source in group["sources"][1:]:
            a, b = sorted((find(first), find(source["id"])))
            parent[b] = a
    components = defaultdict(list)
    for sid in sorted(sources):
        components[find(sid)].append(sid)
    if len(components) < 3:
        raise ValueError("Need at least three independent article components")
    ordered = sorted(components.values(),
                     key=lambda ids: sha256((seed + ":" + ",".join(ids)).encode("utf-8")))
    holdout = max(1, len(ordered) // 10)
    assignments = {}
    component_records = []
    for i, ids in enumerate(ordered):
        split = "test" if i < holdout else "valid" if i < 2 * holdout else "train"
        assignments.update({sid: split for sid in ids})
        component_records.append({"articleIds": ids, "split": split})
    for group in groups.values():
        group_splits = {assignments[s["id"]] for s in group["sources"]}
        if len(group_splits) != 1:
            raise ValueError("Shared section crosses article splits")
        group["split"] = group_splits.pop()
    return assignments, component_records


def export(output, seed):
    cache = (ROOT / ".cache/training").resolve()
    output = output.resolve()
    if cache not in output.parents or output == cache / "research-v1":
        raise ValueError("Use a separate encyclopedia directory under .cache/training/")
    index_path = ROOT / "public/data/encyclopedia/index.json"
    sources, groups, counts = load_sections(index_path)
    assignments, components = assign_splits(sources, groups, seed)
    output.mkdir(parents=True, exist_ok=True)
    stats, used = {}, {}
    for split in SPLITS:
        records = sorted((g for g in groups.values() if g["split"] == split),
                         key=lambda g: (g["sources"][0]["id"], g["sources"][0]["sectionOrdinal"]))
        data_path = output / f"{split}.jsonl"
        provenance_path = output / f"{split}.provenance.jsonl"
        # Attribution travels with every data record as well as the sidecar:
        # losing a separate manifest must not erase article credit.
        with data_path.open("w", encoding="utf-8") as data_file, \
                provenance_path.open("w", encoding="utf-8") as provenance_file:
            for record in records:
                attribution = {
                    "id": record["id"],
                    "textSha256": sha256(record["text"].encode("utf-8")),
                    "normalizedTextSha256": record["normalizedTextSha256"],
                    "license": LICENSE,
                    "licenseUrl": LICENSE_URL,
                    "attribution": "Wikipedia contributors",
                    "sources": record["sources"],
                }
                data_file.write(json.dumps({"text": record["text"], **attribution},
                                           ensure_ascii=False) + "\n")
                provenance_file.write(json.dumps(attribution, ensure_ascii=False) + "\n")
        used[split] = {s["id"] for r in records for s in r["sources"]}
        stats[split] = {
            "sections": len(records), "words": sum(len(r["text"].split()) for r in records),
            "articleIds": sorted(used[split]), "articleCount": len(used[split]),
            "sectionCategoryCounts": dict(Counter(r["sources"][0]["sectionCategory"] for r in records)),
            "sha256": sha256(data_path.read_bytes()),
            "provenanceSha256": sha256(provenance_path.read_bytes()),
        }
    if any(used[a] & used[b] for a, b in (("train", "valid"), ("train", "test"), ("valid", "test"))):
        raise ValueError("Article overlap between splits")
    duplicates = [g for g in groups.values() if len(g["sources"]) > 1]
    manifest = {
        "schemaVersion": 1, "dataset": "wikipedia-encyclopedia-sections-v1",
        "purpose": "Attributed continued-pretraining candidate text; no reviewed answers or trained weights.",
        "license": LICENSE, "licenseUrl": LICENSE_URL,
        "attribution": "Wikipedia contributors",
        "licenseTermsUrl": "https://creativecommons.org/licenses/by-sa/4.0/legalcode.en",
        "wikimediaTermsUrl": "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content",
        "seed": seed, **counts,
        "uniqueSections": len(groups),
        "duplicateOccurrencesRemoved": sum(len(g["sources"]) - 1 for g in duplicates),
        "duplicateGroups": len(duplicates),
        "crossArticleDuplicateGroups": sum(len({s["id"] for s in g["sources"]}) > 1 for g in duplicates),
        "splitUnit": "Connected component of articles sharing identical normalized sections",
        "splitPolicy": "Seeded SHA256 component order, approximately 80/10/10 by component count; no religious ranking or stratification.",
        "deduplication": "NFC Unicode normalization and whitespace collapsing for comparison only. Export retains the first article's exact stored section text and all duplicate provenance.",
        "components": components, "splits": stats,
        "sources": [{**s, "split": assignments[sid]} for sid, s in sorted(sources.items())],
        "includedFields": ["articles[*].sections[*].text"],
        "excluded": ["summary", "studyNotes", "notes", "references", "externalReferences",
                     "Linked modern paper bodies", "Generated Q&A", "Images and media"],
        "modifications": "Previously abridged plain-text sections selected and deduplicated; dataset partitioned by article component. No paraphrases or answers generated.",
        "limitations": [
            "Article-level separation and exact normalized deduplication do not eliminate paraphrases, repeated quotations inside larger sections, shared facts or pretraining contamination.",
            "Wikipedia is secondary reference material, not a theological authority or an exhaustively verified archaeology corpus.",
            "The collection is predominantly geography and is not a balanced survey of Christian, Jewish or Muslim traditions.",
            "Section text may contain attributed inline quotations already present in Wikipedia. Bibliographic pointers are not downloads or verified endorsements of cited papers.",
            "Share retained/adapted text datasets with applicable CC BY-SA attribution, license and modification notices; retain this manifest and per-record provenance.",
            "Trained-model distribution needs a separate license analysis. The base model's Apache-2.0 license does not settle obligations arising from this dataset.",
            "No model trained. This dataset is intentionally separate from the public-domain historical-text training recipe.",
        ],
    }
    dump_json(output / "rights-and-splits.json", manifest)
    (output / "ATTRIBUTION.md").write_text(
        "# Wikipedia encyclopedia training-text export\n\n"
        "Text by Wikipedia contributors, retained under [CC BY-SA 4.0]"
        "(https://creativecommons.org/licenses/by-sa/4.0/). Article titles, pinned "
        "revisions, contributor-history links, original modification notices and "
        "source hashes appear in every JSONL record and its provenance sidecar. "
        "Keep these attributions and rights-and-splits.json with redistributed data.\n\n"
        "Changes: selected existing abridged plain-text sections; deduplicated sections "
        "using NFC/whitespace comparison; partitioned articles without generating answers. "
        "Retained text is unchanged from its selected stored source section. Adapted text "
        "dataset contributions are distributed under CC BY-SA 4.0. No endorsement by "
        "Wikipedia contributors or Wikimedia is implied.\n\n"
        "See the [license legal code](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en) "
        "and [Wikimedia reuse terms](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content). "
        "Review model-distribution licensing separately; this export does not establish "
        "a license for trained weights. It contains no trained model.\n",
        encoding="utf-8",
    )
    for split, stat in stats.items():
        print(f"{split}: {stat['sections']:,} unique sections, {stat['words']:,} words, {stat['articleCount']} articles")
    print(f"Removed {manifest['duplicateOccurrencesRemoved']} duplicate occurrences; "
          f"{manifest['crossArticleDuplicateGroups']} groups span articles.")
    print(f"Exported to {output}; no model trained.")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/training/encyclopedia-v1")
    parser.add_argument("--seed", default="scripture-encyclopedia-v1")
    args = parser.parse_args()
    export(args.output, args.seed)


if __name__ == "__main__":
    main()
