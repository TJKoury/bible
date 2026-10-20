#!/usr/bin/env python3
"""Download attributed source snapshots and generate the browser's static library.

Python standard library only. Original downloads are cached, never scraped from
reader sites. Each source URL, revision and SHA-256 is recorded in sources.json.
"""
import csv
import hashlib
import io
import json
import re
import shutil
import urllib.request
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
OUT = ROOT / "public/data"
LICENSES = ROOT / "public/licenses"
for directory in (CACHE, OUT, LICENSES):
    directory.mkdir(parents=True, exist_ok=True)

BOOK_NAMES = (
    "Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|1 Samuel|2 Samuel|"
    "1 Kings|2 Kings|1 Chronicles|2 Chronicles|Ezra|Nehemiah|Esther|Job|Psalms|Proverbs|"
    "Ecclesiastes|Song of Solomon|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|"
    "Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|"
    "Matthew|Mark|Luke|John|Acts|Romans|1 Corinthians|2 Corinthians|Galatians|Ephesians|"
    "Philippians|Colossians|1 Thessalonians|2 Thessalonians|1 Timothy|2 Timothy|Titus|"
    "Philemon|Hebrews|James|1 Peter|2 Peter|1 John|2 John|3 John|Jude|Revelation"
).split("|")
USFM = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO "
        "ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL "
        "MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB "
        "JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
OSIS = ("Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth "
        "Job Ps Prov Eccl Song Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph "
        "Hag Zech Mal Matt Mark Luke John Acts Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess "
        "1Tim 2Tim Titus Phlm Heb Jas 1Pet 2Pet 1John 2John 3John Jude Rev").split()
EXTRA = ["Tobit", "Judith", "Wisdom", "Sirach", "Baruch", "1 Maccabees", "2 Maccabees",
         "Prayer of Manasses", "1 Esdras", "2 Esdras", "Additional Psalm", "Laodiceans"]
ALL_NAMES = BOOK_NAMES + EXTRA
USFM_IDS = {s: i + 1 for i, s in enumerate(USFM)}
OSIS_IDS = {s: i + 1 for i, s in enumerate(OSIS)}

EDITIONS = [
    ("BSB", "Berean Standard Bible", "Modern English", "Public domain (CC0)"),
    ("KJV", "King James Version", "Traditional English", "Public domain in the US; UK Crown rights apply"),
    ("ASV", "American Standard Version", "1901", "Public domain"),
    ("BBE", "Bible in Basic English", "1949 / 1964", "Public domain"),
    ("Darby", "Darby Bible", "1889", "Public domain"),
    ("YLT", "Young’s Literal Translation", "1898", "Public domain"),
    ("DRC", "Douay–Rheims Bible", "Challoner revision · includes deuterocanon", "Public domain"),
    ("Webster", "Webster Bible", "1833", "Public domain"),
    ("JPS", "Jewish Publication Society", "1917 · Tanakh", "Public domain"),
    ("Rotherham", "Rotherham’s Emphasized Bible", "1902", "Public domain"),
    ("Geneva1599", "Geneva Bible", "1599", "Public domain"),
    ("NHEB", "New Heart English Bible", "Modern English", "Public domain"),
    ("CPDV", "Catholic Public Domain Version", "2009 · includes deuterocanon", "Public domain"),
]
sources = {}
lock_file = ROOT / "sources.lock.json"
lock = json.loads(lock_file.read_text()) if lock_file.exists() else {}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")


def request(url):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "ScriptureStudy/1.0"}), timeout=120
    ).read()


def revision(repo, branch):
    if repo not in lock:
        lock[repo] = json.loads(request(f"https://api.github.com/repos/{repo}/commits/{branch}"))["sha"]
        write_json(lock_file, lock)
    return lock[repo]


def raw_url(repo, branch, path):
    return f"https://raw.githubusercontent.com/{repo}/{revision(repo, branch)}/{path}"


def download(name, url):
    path = CACHE / name
    if not path.exists():
        data = request(url)
        temp = path.with_suffix(path.suffix + ".part")
        temp.write_bytes(data)
        temp.replace(path)
    data = path.read_bytes()
    sources[name] = {"url": url, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return data


def book_id(name):
    name = re.sub(r"^III ", "3 ", name)
    name = re.sub(r"^II ", "2 ", name)
    name = re.sub(r"^I ", "1 ", name)
    name = {"Revelation of John": "Revelation", "Song of Songs": "Song of Solomon"}.get(name, name)
    if name not in ALL_NAMES:
        raise ValueError(f"Unmapped book: {name}")
    return ALL_NAMES.index(name) + 1


def save_edition(code, title, subtitle, license_name, books, source_url, native="english"):
    metadata = []
    count = 0
    empty = []
    # Source exporters can emit entire placeholder books; do not advertise these
    # as available text. Keep isolated gaps explicitly marked in real chapters.
    books = {bid: {c: vs for c, vs in cs.items() if any(t.strip() for t in vs.values())}
             for bid, cs in books.items()}
    books = {bid: cs for bid, cs in books.items() if cs}
    for bid, chapters in books.items():
        chapters = dict(sorted(chapters.items(), key=lambda x: int(x[0])))
        for chapter, verses in chapters.items():
            chapters[chapter] = dict(sorted(verses.items(), key=lambda x: int(x[0])))
            count += sum(bool(text.strip()) for text in verses.values())
            empty.extend(f"{bid}.{chapter}.{v}" for v, text in verses.items() if not text.strip())
        write_json(OUT / "translations" / code / f"{bid}.json", chapters)
        metadata.append({"id": bid, "chapters": [int(x) for x in chapters]})
    payload = {"id": code, "title": title, "subtitle": subtitle, "license": license_name,
               "source": source_url, "books": metadata, "verses": count, "numbering": native,
               "sourceGaps": empty}
    download_path = OUT / "downloads" / f"{code}.zip"
    download_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(download_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(f"{code}.json", json.dumps({
            "edition": payload, "attribution": source_url, "license": license_name, "books": books
        }, ensure_ascii=False, separators=(",", ":")) + "\n")
    (OUT / "downloads" / f"{code}.json").unlink(missing_ok=True)
    print(f"{code}: {len(books)} books, {count:,} verses", flush=True)
    return payload


def download_translation(edition):
    code, title, subtitle, license_name = edition
    if code == "KJV":
        repo = "thiagobodruk/bible"
        url = raw_url(repo, "master", "json/en_kjv.json")
        data = json.loads(download("kjv-complete.json", url).decode("utf-8-sig"))
        assert len(data) == 66
        books = {i + 1: {c + 1: {v + 1: text for v, text in enumerate(chapter)}
                        for c, chapter in enumerate(book["chapters"])} for i, book in enumerate(data)}
        (LICENSES / "KJV-repository-MIT.txt").write_bytes(download("kjv-license.txt", raw_url(repo, "master", "LICENSE")))
        return save_edition(code, title, subtitle, license_name, books, url)
    repo = "scrollmapper/bible_databases"
    url = raw_url(repo, "master", f"formats/json/{code}.json")
    data = json.loads(download(f"translation-{code}.json", url))
    notice = download(f"notice-{code}.md", raw_url(repo, "master", f"sources/en/{code}/README.md"))
    (LICENSES / f"{code}.md").write_bytes(notice)
    books = {}
    for book in data["books"]:
        bid = book_id(book["name"])
        books[bid] = {c["chapter"]: {v["verse"]: v["text"] for v in c["verses"]} for c in book["chapters"]}
    # Native-numbered editions remain readable, with study alignment explicitly unavailable.
    native = "native" if code in ("DRC", "CPDV", "JPS") else "english"
    return save_edition(code, title, subtitle, license_name, books, url, native)


def download_web():
    repo = "TehShrike/world-english-bible"
    rev = revision(repo, "master")
    files = json.loads(request(f"https://api.github.com/repos/{repo}/contents/json?ref={rev}"))
    by_name = {re.sub(r"[^a-z0-9]", "", n.lower()): i + 1 for i, n in enumerate(BOOK_NAMES)}
    books = {}
    def parse(item):
        filename = item["name"]
        if not filename.endswith(".json"):
            return
        key = re.sub(r"[^a-z0-9]", "", filename[:-5].lower())
        key = {"psalm": "psalms", "songofsolomon": "songofsolomon"}.get(key, key)
        if key not in by_name:
            raise ValueError(f"Unknown WEB filename {filename}")
        rows = json.loads(download("WEB-" + filename, raw_url(repo, "master", "json/" + filename)))
        chapters = defaultdict(dict)
        for row in rows:
            if row.get("type") in ("paragraph text", "line text") and row.get("chapterNumber") and row.get("verseNumber"):
                c, v = row["chapterNumber"], row["verseNumber"]
                chapters[c][v] = chapters[c].get(v, "") + row["value"]
        return by_name[key], {c: {v: re.sub(r"\s+", " ", t).strip() for v, t in vs.items()} for c, vs in chapters.items()}
    for result in ThreadPoolExecutor(max_workers=8).map(parse, files):
        if result:
            books[result[0]] = result[1]
    return save_edition("WEB", "World English Bible", "Modern English", "Public domain",
                        dict(sorted(books.items())), f"https://github.com/{repo}/tree/{rev}")


def parse_vrs(text):
    """Map English verse coordinates to BHS coordinates; preserve many-to-one mappings."""
    mapping = defaultdict(list)
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        sides = []
        for side in line.split("="):
            m = re.fullmatch(r"(\w+) (\d+):(\d+)(?:-(\d+))?", side.strip())
            if not m or m[1] not in USFM_IDS:
                sides = []
                break
            bid, ch, start, end = USFM_IDS[m[1]], int(m[2]), int(m[3]), int(m[4] or m[3])
            sides.append([f"{bid}.{ch}.{v}" for v in range(start, end + 1)])
        if len(sides) != 2:
            continue
        left, right = sides
        if len(left) == len(right):
            pairs = zip(left, right)
        elif len(left) == 1:
            pairs = ((left[0], r) for r in right)
        elif len(right) == 1:
            pairs = ((l, right[0]) for l in left)
        else:
            raise ValueError(f"Ambiguous verse mapping: {line}")
        for english, original in pairs:
            if original not in mapping[english]:
                mapping[english].append(original)
    return dict(mapping)


def original_languages():
    verse_map_text = download("eng.vrs.txt", raw_url("sillsdev/libpalaso", "master",
                                                   "SIL.Scripture/Resources/eng.vrs.txt")).decode("utf-8-sig")
    verse_map = parse_vrs(verse_map_text)
    write_json(OUT / "verse-map.json", verse_map)
    words = 0
    totals = {}
    for lang, repo, filename in (
        ("greek", "Clear-Bible/macula-greek", "SBLGNT/tsv/macula-greek-SBLGNT.tsv"),
        ("hebrew", "Clear-Bible/macula-hebrew", "WLC/tsv/macula-hebrew.tsv"),
    ):
        rev = revision(repo, "main")
        url = raw_url(repo, "main", filename)
        if lang == "hebrew":
            url = f"https://media.githubusercontent.com/media/{repo}/{rev}/{filename}"
        data = download(lang + ".tsv", url).decode()
        if data.startswith("version https://git-lfs"):
            raise ValueError("Git LFS pointer returned instead of Hebrew data")
        notice = download(lang + "-license.md", raw_url(repo, "main", "LICENSE.md"))
        (LICENSES / f"macula-{lang}.md").write_bytes(notice)
        books = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        lemmas = defaultdict(lambda: {"refs": [], "forms": [], "glosses": [], "count": 0, "strong": ""})
        for row in csv.DictReader(io.StringIO(data), delimiter="\t"):
            m = re.fullmatch(r"(\w+) (\d+):(\d+)!(\d+)", row["ref"])
            if not m:
                raise ValueError(f"Unrecognized reference {row['ref']}")
            bid, c, v = USFM_IDS[m[1]], int(m[2]), int(m[3])
            lemma = row["lemma"]
            strong = row.get("strong") or row.get("strongnumberx", "")
            strong = ("G" if lang == "greek" else "H") + strong.lstrip("0") if strong else ""
            # Only CC BY morphology and gloss fields; no UBS semantic-domain data.
            word = {
                "text": row["text"], "lemma": lemma, "gloss": row.get("gloss") or row.get("english", ""),
                "transliteration": row.get("transliteration", ""),
                "strong": strong, "morph": row["morph"], "pos": row.get("pos") or row["class"],
                "grammar": " · ".join(row.get(k, "") for k in
                                      ("stem", "person", "tense", "voice", "mood", "case", "gender", "number", "state")
                                      if row.get(k)),
                "after": row.get("after", ""), "language": row.get("lang", "G"),
            }
            books[bid][c][v].append(word)
            words += 1
            if lemma:
                entry = lemmas[lemma]
                entry["count"] += 1
                ref = f"{bid}.{c}.{v}"
                if not entry["refs"] or entry["refs"][-1] != ref:
                    entry["refs"].append(ref)
                for field, value in (("forms", word["text"]), ("glosses", word["gloss"])):
                    if value and value not in entry[field] and len(entry[field]) < 12:
                        entry[field].append(value)
                entry["strong"] = strong
        for bid, chapters in books.items():
            for c, verses in chapters.items():
                write_json(OUT / "original" / str(bid) / f"{c}.json", verses)
        # Sharded concordance keeps initial study requests small.
        shards = defaultdict(dict)
        for lemma, entry in lemmas.items():
            shard = hashlib.sha256(lemma.encode()).hexdigest()[:2]
            shards[shard][lemma] = entry
        for shard, entries in shards.items():
            write_json(OUT / "lemmas" / lang / f"{shard}.json", entries)
        totals[lang] = {"lemmas": len(lemmas), "words": sum(e["count"] for e in lemmas.values())}
        print(f"{lang}: {totals[lang]}", flush=True)
    return totals


def cross_references():
    data = download("cross-references.zip", "https://a.openbible.info/data/cross-references.zip")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        text = z.read("cross_references.txt").decode()
    def coordinate(ref):
        b, c, v = ref.split(".")
        return f"{OSIS_IDS[b]}.{int(c)}.{int(v)}"
    books = defaultdict(lambda: defaultdict(list))
    count = 0
    for row in csv.reader(text.splitlines()[1:], delimiter="\t"):
        if len(row) < 3:
            continue
        start = coordinate(row[0])
        targets = row[1].split("-")
        target = coordinate(targets[0])
        end = coordinate(targets[1]) if len(targets) > 1 else None
        books[start.split(".")[0]][start].append({"ref": target, "end": end, "votes": int(row[2])})
        count += 1
    for bid, refs in books.items():
        for values in refs.values():
            values.sort(key=lambda x: -x["votes"])
        write_json(OUT / "crossrefs" / f"{bid}.json", refs)
    (LICENSES / "openbible.txt").write_text(
        text.splitlines()[0] + "\nCross-reference data from OpenBible.info.\n"
        "https://www.openbible.info/labs/cross-references/\n"
        "Creative Commons Attribution: https://creativecommons.org/licenses/by/4.0/\n")
    return count


def package_originals():
    """Downloadable, attributed archives containing the same study data as the app."""
    for language, book_ids in (("hebrew", range(1, 40)), ("greek", range(40, 67))):
        target = OUT / "downloads" / f"{language}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for bid in book_ids:
                for path in sorted((OUT / "original" / str(bid)).glob("*.json")):
                    archive.write(path, path.relative_to(OUT).as_posix())
            for path in sorted((OUT / "lemmas" / language).glob("*.json")):
                archive.write(path, path.relative_to(OUT).as_posix())
            for path in sorted(LICENSES.iterdir()):
                if language in path.name or path.name in ("SBLGNT.txt", "SIL.txt"):
                    archive.write(path, "licenses/" + path.name)
            archive.write(OUT / "verse-map.json", "verse-map.json")
            archive.writestr("README.txt",
                f"MACULA {language.title()} Linguistic Datasets\n"
                f"https://github.com/Clear-Bible/macula-{language}/\n"
                "CC BY 4.0. See enclosed licenses for source-specific attributions.\n"
                "Modified: converted to chapter JSON and lemma concordance shards.\n"
                "Book IDs follow the Protestant 1–66 order. Original chapter/verse numbering is retained.\n"
                "verse-map.json maps English-numbered references to original Hebrew references.\n"
                "English glosses are contextual aids, not an exhaustive dictionary.\n"
                "UBS semantic-domain fields have not been included.\n")


def main():
    # Resolve revisions serially before concurrent downloads update the lockfile.
    for repo, branch in (("scrollmapper/bible_databases", "master"), ("TehShrike/world-english-bible", "master"),
                         ("Clear-Bible/macula-greek", "main"), ("Clear-Bible/macula-hebrew", "main"),
                         ("sillsdev/libpalaso", "master"), ("Faithlife/SBLGNT", "master")):
        revision(repo, branch)
    revision("thiagobodruk/bible", "master")
    translations = list(ThreadPoolExecutor(max_workers=6).map(download_translation, EDITIONS))
    translations.insert(1, download_web())
    original_stats = original_languages()
    xrefs = cross_references()
    for name, url in (
        ("scrollmapper-MIT.txt", raw_url("scrollmapper/bible_databases", "master", "LICENSE")),
        ("SBLGNT.txt", raw_url("Faithlife/SBLGNT", "master", "LICENSE")),
        ("SIL.txt", raw_url("sillsdev/libpalaso", "master", "LICENSE")),
    ):
        (LICENSES / name).write_bytes(download(name, url))
    write_json(OUT / "catalog.json", {
        "books": [{"id": i + 1, "name": n, "testament": "OT" if i < 39 else "NT" if i < 66 else "DC"}
                  for i, n in enumerate(ALL_NAMES)],
        "translations": translations, "original": original_stats, "crossReferences": xrefs,
    })
    write_json(OUT / "sources.json", sources)
    expected = {edition["id"]: {str(b["id"]) for b in edition["books"]} for edition in translations}
    for directory in (OUT / "translations").iterdir():
        if directory.name not in expected:
            shutil.rmtree(directory)
            (OUT / "downloads" / f"{directory.name}.json").unlink(missing_ok=True)
            (OUT / "downloads" / f"{directory.name}.zip").unlink(missing_ok=True)
        else:
            for path in directory.glob("*.json"):
                if path.stem not in expected[directory.name]:
                    path.unlink()
    package_originals()
    print(f"Ready: {len(translations)} editions, {xrefs:,} cross-references.", flush=True)


if __name__ == "__main__":
    main()
