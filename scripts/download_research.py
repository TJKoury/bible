#!/usr/bin/env python3
"""Download a documented historical research corpus, with no model-generated Q&A.

Raw files stay in .cache/research. Public JSON contains normalized, non-overlapping
passages and original line/verse locators. Existing SHA256 locks must match unless
--refresh is explicitly used to accept a changed upstream file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public/data/research"
CACHE = ROOT / ".cache/research"
LICENSES = ROOT / "public/licenses"
PD = "Public domain in the USA; see source edition and local copyright law."
PG_LICENSE = "https://www.gutenberg.org/policy/license.html"


def pg(id, number, title, author, tradition, perspective, date, translator="", notes=""):
    return dict(id=id, gutenbergId=number, title=title, author=author,
                tradition=tradition, perspective=perspective, publicationDate=date,
                translator=translator, sourceUrl=f"https://www.gutenberg.org/ebooks/{number}",
                downloadUrl=f"https://www.gutenberg.org/cache/epub/{number}/pg{number}.txt",
                license=PD, licenseUrl=PG_LICENSE, sourceType="historical primary text",
                trainingEligible=True, coverageNotes=notes,
                cacheFile=f"pg{number}.txt")


SOURCES = [
    pg("augustine-confessions", 3296, "Confessions", "Augustine of Hippo",
       "Christianity", "Patristic / Latin Christian", "c. 397–400; translation 1838",
       "E. B. Pusey", "Shared reception across Christian traditions; not exclusively owned by a modern denomination."),
    pg("aquinas-god", 17611, "Summa Theologica I, Questions 1–26", "Thomas Aquinas",
       "Christianity", "Roman Catholic / Thomist", "13th century; early 20th-century Dominican translation",
       "Fathers of the English Dominican Province",
       "Selection on sacred doctrine, God, providence, and predestination. Objections are arguments Aquinas answers, not necessarily his positions."),
    pg("luther-catechism", 1722, "Large Catechism", "Martin Luther",
       "Christianity", "Lutheran", "1529; English edition 1921",
       "F. Bente and W. H. T. Dau"),
    pg("calvin-institutes-2", 64392, "Institutes of the Christian Religion, Volume II",
       "John Calvin", "Christianity", "Reformed", "1559; John Allen translation, sixth American edition",
       "John Allen", "Volume II only: not the complete Institutes. Historical polemics describe this author's position."),
    pg("wesley-sermons-1", 59743, "Works, Volume I: Sermons", "John Wesley",
       "Christianity", "Wesleyan / Methodist", "1771 collected edition", "",
       "First volume only; includes editorial front matter and quoted opponents."),
    pg("pirke-avot", 8547, "Pirke Avot: The Sayings of the Jewish Fathers",
       "Rabbinic sages; edited and translated by Joseph I. Gorfinkle",
       "Judaism", "Rabbinic ethics", "Ancient collection; English edition 1913",
       "Joseph I. Gorfinkle", "Includes the translator's introduction and notes; distinguish them from the ancient sayings."),
    pg("maimonides-guide", 73584, "The Guide for the Perplexed", "Moses Maimonides",
       "Judaism", "Medieval Jewish philosophy / Maimonidean", "c. 1190; English edition 1910",
       "Michael Friedländer", "Includes translator's analysis and introduction; not a statement of every Jewish tradition."),
    pg("kohler-theology", 32722, "Jewish Theology, Systematically and Historically Considered",
       "Kaufmann Kohler", "Judaism", "Reform Jewish / historical theology", "1918", "",
       "A historical Reform perspective, not a neutral proxy for all Judaism."),
    pg("ghazali-confessions", 58977, "The Confessions of Al Ghazzali", "Abu Hamid al-Ghazali",
       "Islam", "Sunni / Sufi", "12th century; English edition 1909",
       "Claud Field", "Historical translation with an editor's introduction; terminology is dated."),
    pg("averroes-philosophy", 65708, "The Philosophy and Theology of Averroes", "Ibn Rushd (Averroes)",
       "Islam", "Andalusian Islamic philosophy", "12th century; English edition 1921",
       "Muhammad Jamil al-Rahman", "Philosophical arguments and critiques of other schools are the author's, not a consensus of Islam."),
    pg("ameer-ali-islam", 70136, "Islâm", "Syed Ameer Ali",
       "Islam", "Muslim modernist / apologetic", "1909", "",
       "An author's historical apologetic presentation, not a comprehensive statement of Sunni or Shi'a doctrine."),
    pg("quran-pickthall", 16955, "The Meaning of the Glorious Koran — Pickthall translation",
       "Qur'an; English interpretation by Marmaduke Pickthall",
       "Islam", "Qur'an / Muslim English translation", "1930", "Marmaduke Pickthall",
       "Only the Pickthall text is extracted from the three-translation source. English interpretation is not the Arabic Qur'an. Four malformed source locators are normalized using their chapter and sequential position: 0.033→17:33, 039.04→39:46, 04.032→45:32, 05.026→56:26; wording is unchanged."),
    dict(id="philaret-catechism", title="Longer Catechism of the Orthodox, Catholic, Eastern Church",
         author="Philaret of Moscow", translator="R. W. Blackmore; Philip Schaff, editor",
         tradition="Christianity", perspective="Eastern Orthodox / Russian catechism",
         publicationDate="1830; English translation 1845; collected edition 1919",
         sourceUrl="https://ccel.org/ccel/schaff/creeds2.html",
         downloadUrl="https://ccel.org/ccel/s/schaff/creeds2/cache/creeds2.txt",
         license=PD, licenseUrl="https://ccel.org/about/copyright.html",
         sourceType="historical primary text", trainingEligible=True, cacheFile="creeds2.txt",
         coverageNotes="Complete catechism excerpted from Schaff's collection, excluding his introductory evaluation. A historical Russian Orthodox source, not every Orthodox jurisdiction."),
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def download(source, locks, refresh=False):
    path = CACHE / source["cacheFile"]
    if refresh or not path.exists():
        req = urllib.request.Request(source["downloadUrl"], headers={
            "User-Agent": "ScriptureStudy/1.0 (historical public-domain corpus)"})
        with urllib.request.urlopen(req, timeout=90) as response:
            data = response.read()
        path.write_bytes(data)
    data = path.read_bytes()
    sha = digest(data)
    previous = locks.get(source["id"], {}).get("sha256")
    if previous and sha != previous and not refresh:
        raise ValueError(f"Source changed: {source['id']}. Inspect before using --refresh.")
    return data.decode("utf-8-sig"), sha


def content_bounds(source, lines):
    if source["id"] == "philaret-catechism":
        start = next(i for i, line in enumerate(lines) if "INTRODUCTION TO THE ORTHODOX CATECHISM." in line)
        end = next(i for i, line in enumerate(lines[start:], start) if "THE OLD CATHOLIC UNION CREEDS." in line)
        return start, end
    start = next(i + 1 for i, line in enumerate(lines) if line.startswith("*** START OF"))
    end = next(i for i, line in enumerate(lines) if line.startswith("*** END OF"))
    if source["id"] == "aquinas-god":
        # Deliberately retain the complete question/objection/reply structures.
        start = next(i for i in range(start, end) if lines[i].strip() == "QUESTION 1")
        end = next(i for i in range(start, end)
                   if lines[i].strip().startswith("TREATISE ON THE MOST HOLY TRINITY"))
    return start, end


def is_heading(text):
    return (len(text) < 160 and len(text.split()) < 22 and (
        bool(re.match(r"^(?:BOOK|PART|CHAPTER|QUESTION|SERMON)\b", text))
        or (text.isupper() and len(text.split()) > 1)
        or text.startswith(("On the ", "Of the ", "The First Commandment", "The Second Commandment"))))


def prose_chunks(source, text):
    lines = text.splitlines()
    start, end = content_bounds(source, lines)
    paragraphs, buffer, begin = [], [], start
    for i in range(start, end + 1):
        line = lines[i].strip() if i < end else ""
        if not line:
            if buffer:
                value = " ".join(buffer)
                if re.search(r"[A-Za-z]", value):
                    paragraphs.append((value, begin + 1, i))
                buffer = []
        elif not re.fullmatch(r"[-_*─━═│┌┐└┘\s]+", line):
            if not buffer:
                begin = i
            buffer.append(line)
    chunks, parts, count, first, last, heading = [], [], 0, 0, 0, ""

    def emit():
        nonlocal parts, count
        if not parts:
            return
        ordinal = len(chunks) + 1
        chunks.append(dict(id=f"{source['id']}:{ordinal}", sourceId=source["id"],
                           ordinal=ordinal, text="\n\n".join(parts), heading=heading,
                           locator=f"Source text lines {first}–{last}",
                           startLine=first, endLine=last))
        parts, count = [], 0

    for paragraph, a, b in paragraphs:
        words = paragraph.split()
        if is_heading(paragraph):
            emit()
            heading = paragraph
        if parts and count + len(words) > 420:
            emit()
        # Exceptionally long paragraphs become consecutive sentence-sized blocks.
        pieces = [paragraph]
        if len(words) > 600:
            pieces, piece = [], []
            for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
                if piece and sum(len(p.split()) for p in piece) + len(sentence.split()) > 420:
                    pieces.append(" ".join(piece))
                    piece = []
                piece.append(sentence)
            if piece:
                pieces.append(" ".join(piece))
        for piece in pieces:
            if parts and count + len(piece.split()) > 520:
                emit()
            if not parts:
                first = a
            parts.append(piece)
            count += len(piece.split())
            last = b
    emit()
    return chunks


def quran_chunks(source, text):
    verses = []
    fixes = {"0.033": (17, 33), "039.04": (39, 46), "04.032": (45, 32), "05.026": (56, 26)}
    for match in re.finditer(r"(?m)^(\d{1,3}\.\d{2,3})\s*\n(.*?)(?=^\d{1,3}\.\d{2,3}\s*$|\Z)", text, re.S | re.M):
        pickthall = re.search(r"(?m)^P: (.*?)(?=\n\s*\nS:)", match[2], re.S)
        if not pickthall:
            raise ValueError(f"Missing Pickthall verse {match[1]}")
        s, v = fixes.get(match[1], tuple(map(int, match[1].split("."))))
        verses.append((s, v, " ".join(pickthall[1].split())))
    if len(verses) != 6236 or len(set((s, v) for s, v, _ in verses)) != 6236:
        raise ValueError(f"Expected 6,236 distinct Quran verses; got {len(verses)}")
    assert sorted(verses) == verses
    assert {s for s, _, _ in verses} == set(range(1, 115))
    for s in range(1, 115):
        numbers = [v for chapter, v, _ in verses if chapter == s]
        assert numbers == list(range(1, len(numbers) + 1)), f"Nonsequential chapter {s}"
    chunks, batch, words = [], [], 0

    def emit():
        nonlocal batch, words
        if not batch:
            return
        ordinal = len(chunks) + 1
        surah, first, _ = batch[0]
        last = batch[-1][1]
        chunks.append(dict(id=f"{source['id']}:{ordinal}", sourceId=source["id"],
                           ordinal=ordinal, text="\n".join(f"{s}:{v} {t}" for s, v, t in batch),
                           locator=f"Qur'an {surah}:{first}" + (f"–{last}" if last != first else ""),
                           heading=f"Surah {surah}", surah=surah, verseStart=first, verseEnd=last))
        batch, words = [], 0

    for s, v, text in verses:
        if batch and (batch[0][0] != s or words + len(text.split()) > 400):
            emit()
        batch.append((s, v, text))
        words += len(text.split())
    emit()
    return chunks


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--refresh", action="store_true", help="Re-download and accept reviewed upstream updates.")
    args = args.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    lock_path = OUT / "sources.lock.json"
    locks = json.loads(lock_path.read_text()) if lock_path.exists() else {}
    all_chunks, manifest, new_locks, notices = [], [], {}, []
    for spec in SOURCES:
        text, sha = download(spec, locks, args.refresh)
        chunks = quran_chunks(spec, text) if spec["id"] == "quran-pickthall" else prose_chunks(spec, text)
        assert chunks and all(c["text"].strip() for c in chunks)
        source = {k: v for k, v in spec.items() if k != "cacheFile"}
        source.update(sha256=sha, revision=f"sha256:{sha}", chunkCount=len(chunks),
                      wordCount=sum(len(c["text"].split()) for c in chunks))
        all_chunks.extend(chunks)
        manifest.append(source)
        new_locks[source["id"]] = dict(url=source["downloadUrl"], sha256=sha,
                                      bytes=len(text.encode("utf-8")))
        notices.append(f"{source['title']}\n{source['author']}\n{source['sourceUrl']}\n"
                       f"{source['license']}\nTranslation: {source['translator']}\n"
                       f"SHA256: {sha}\n")
        print(f"{source['id']}: {len(chunks)} passages, {source['wordCount']:,} words")
    # Include the actual redistribution terms, separate from searchable source text.
    pg_text = (CACHE / "pg1722.txt").read_text()
    pg_footer = pg_text[pg_text.index("*** END OF"):]
    LICENSES.mkdir(parents=True, exist_ok=True)
    (LICENSES / "research-notices.txt").write_text(
        "Historical Research Corpus — source and edition notices\n\n"
        "Public-domain status stated here is for the United States. Historical texts "
        "retain the authors' views and dated terminology; inclusion is not endorsement.\n"
        "Gutenberg files were normalized and split into passages; the original texts "
        "and their licenses remain available at the linked sources. CCEL's source file "
        "identifies its rights as Public Domain. No modern copyrighted journal article "
        "full text is included.\n\n" + "\n".join(notices) + "\n\n" + pg_footer)
    coverage = {tradition: dict(sources=sum(s["tradition"] == tradition for s in manifest),
                               chunks=sum(s["chunkCount"] for s in manifest if s["tradition"] == tradition),
                               words=sum(s["wordCount"] for s in manifest if s["tradition"] == tradition))
                for tradition in ("Christianity", "Judaism", "Islam")}
    result = dict(schemaVersion=1, sources=manifest, coverage=coverage,
                  totalChunks=len(all_chunks), totalWords=sum(s["wordCount"] for s in manifest),
                  completeness="Historical starting collection, not exhaustive or statistically representative.",
                  gaps=["Contemporary scholarship and modern translations require additional permissions.",
                        "Anglican, Anabaptist, Pentecostal, Oriental Orthodox and many other Christian voices are not yet sampled.",
                        "Jewish Conservative, Reconstructionist, Hasidic and contemporary Orthodox voices are not adequately represented.",
                        "Shi'a, Ibadi and contemporary Sunni schools are not adequately represented; a modernist author is not a substitute for them.",
                        "English translations predominate. Translation and editor voices must be distinguished from original authors.",
                        "No quantity of downloaded text establishes doctrinal truth or consensus."],
                  attributionPolicy="Identify the author and historical perspective; distinguish assertion, quotation, objection, reply and editorial survey. Do not infer group consensus from one author.",
                  licenseNotice="/licenses/research-notices.txt",
                  trainingStatus="Downloaded and segmented; no custom language-model weights trained.")
    write_json(OUT / "chunks.json", all_chunks)
    write_json(OUT / "manifest.json", result)
    write_json(lock_path, new_locks)
    print(f"Total public research data: {sum(p.stat().st_size for p in OUT.glob('*')) / 1024**2:.2f} MiB")


if __name__ == "__main__":
    main()
