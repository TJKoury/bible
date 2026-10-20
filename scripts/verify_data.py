#!/usr/bin/env python3
"""Verify shipped metadata, texts, concordance targets and download archives."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public/data"


def read(path):
    return json.loads(path.read_text())


def verify():
    catalog = read(DATA / "catalog.json")
    assert len(catalog["translations"]) == 14
    texts = 0
    for edition in catalog["translations"]:
        total = 0
        gaps = []
        for metadata in edition["books"]:
            bid = metadata["id"]
            chapters = read(DATA / "translations" / edition["id"] / f"{bid}.json")
            assert metadata["chapters"] == [int(c) for c in chapters]
            assert all(any(t.strip() for t in vs.values()) for vs in chapters.values())
            for c, verses in chapters.items():
                for v, text in verses.items():
                    assert isinstance(text, str)
                    if text.strip():
                        total += 1
                    else:
                        gaps.append(f"{bid}.{c}.{v}")
        assert total == edition["verses"], edition["id"]
        assert gaps == edition["sourceGaps"], edition["id"]
        with zipfile.ZipFile(DATA / "downloads" / f"{edition['id']}.zip") as archive:
            assert archive.testzip() is None
            download = json.loads(archive.read(f"{edition['id']}.json"))
            assert download["edition"] == edition
            assert len(download["books"]) == len(edition["books"])
        texts += total
    original_lemmas = {}
    for book in (DATA / "original").iterdir():
        for chapter in book.glob("*.json"):
            for v, words in read(chapter).items():
                original_lemmas[f"{book.name}.{chapter.stem}.{v}"] = {w["lemma"] for w in words}
    for language in ("hebrew", "greek"):
        lemma_count = 0
        word_count = 0
        for shard in (DATA / "lemmas" / language).glob("*.json"):
            for lemma, entry in read(shard).items():
                assert hashlib.sha256(lemma.encode()).hexdigest()[:2] == shard.stem
                assert len(entry["refs"]) == len(set(entry["refs"])), lemma
                assert all(lemma in original_lemmas.get(ref, set()) for ref in entry["refs"]), lemma
                lemma_count += 1
                word_count += entry["count"]
        assert catalog["original"][language] == {"lemmas": lemma_count, "words": word_count}
        with zipfile.ZipFile(DATA / "downloads" / f"{language}.zip") as archive:
            assert archive.testzip() is None
            assert "README.txt" in archive.namelist()
            assert f"licenses/macula-{language}.md" in archive.namelist()
    xrefs = sum(len(refs) for path in (DATA / "crossrefs").glob("*.json") for refs in read(path).values())
    assert xrefs == catalog["crossReferences"]
    for entry in read(DATA / "sources.json").values():
        assert entry["url"].startswith("https://")
        assert len(entry["sha256"]) == 64
        assert entry["bytes"] > 0
    print(f"Verified: 14 editions / {texts:,} nonempty verses; {len(original_lemmas):,} original-language verse entries; {xrefs:,} cross-references; all concordance targets and ZIPs.")


if __name__ == "__main__":
    verify()
