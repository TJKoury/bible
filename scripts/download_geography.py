#!/usr/bin/env python3
"""Build attributed, revision-pinned geography and Wikipedia study resources.

Only Python's standard library is required. Raw responses are cached outside the
public directory. Normal runs preserve previously imported Wikipedia revisions;
--refresh asks for current revisions. --limit limits geographic article requests
(the named-person/object seed set is always included).

Wikipedia prose is an abridged reference corpus, not peer-reviewed annotation or
an exhaustive archaeological catalog. No third-party article bodies or images
are copied. Block quotations, tables and navigation are omitted.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import html
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import time
import threading
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "geography"
GEO = ROOT / "public" / "data" / "geography"
ENC = ROOT / "public" / "data" / "encyclopedia"
LICENSES = ROOT / "public" / "licenses"
COMMIT = "7eb18a5ee62f27b9b93bd6689ea272d76dd23b8f"
REPO = "https://github.com/openbibleinfo/Bible-Geocoding-Data"
RAW = f"https://raw.githubusercontent.com/openbibleinfo/Bible-Geocoding-Data/{COMMIT}"
HASHES = {
    "ancient": "b8187aa4737e8517ccc090f765d2be11da4c548cd2a59d3cdcb62e952cb8c0f2",
    "modern": "da731f6e110bac4ea66a9f037a0a31cfb11c4f1efc1206aa9e109092b2c60087",
    "source": "b93709cfd947430a3befe3a02a82787ef589c3223c903f4f234adaa46727856a",
}
HEADERS = {"User-Agent": "ScriptureStudy/1.0 (open-source study reader; https://github.com/TJKoury/bible)"}
WIKI_LICENSE = "https://creativecommons.org/licenses/by-sa/4.0/"
GEO_LICENSE = "https://creativecommons.org/licenses/by/4.0/"
NETWORK_LOCK = threading.Lock()
LAST_REQUEST = 0.0

# Aliases here are deliberately qualified where the short name is ambiguous.
# Search may match title words; these aliases are safe labels, not proof that
# every occurrence of an unqualified name refers to this person.
SEEDS = {
    "Saint Peter": ("person", ["Simon Peter", "Saint Peter", "Peter the Apostle"]),
    "Andrew the Apostle": ("person", ["Andrew the Apostle"]),
    "Philip the Apostle": ("person", ["Philip the Apostle"]),
    "Philip the Tetrarch": ("person", ["Philip the Tetrarch", "Herod Philip II"]),
    "Philip the Evangelist": ("person", ["Philip the Evangelist"]),
    "John the Baptist": ("person", ["John the Baptist"]),
    "John the Apostle": ("person", ["John the Apostle"]),
    "John the Evangelist": ("person", ["John the Evangelist"]),
    "Jesus": ("person", ["Jesus of Nazareth", "Jesus Christ"]),
    "Paul the Apostle": ("person", ["Paul the Apostle", "Saul of Tarsus"]),
    "Moses": ("person", ["Moses"]),
    "Abraham": ("person", ["Abraham", "Abram"]),
    "Isaac": ("person", ["Isaac"]),
    "Ishmael": ("person", ["Ishmael"]),
    "Jacob": ("person", ["Jacob the patriarch"]),
    "Esau": ("person", ["Esau"]),
    "Sarah": ("person", ["Sarah", "Sarai"]),
    "Hagar": ("person", ["Hagar"]),
    "Rebecca (biblical figure)": ("person", ["Rebekah"]),
    "Joseph (Genesis)": ("person", ["Joseph son of Jacob"]),
    "Joseph (father of Jesus)": ("person", ["Joseph husband of Mary"]),
    "Mary, mother of Jesus": ("person", ["Mary mother of Jesus"]),
    "Mary Magdalene": ("person", ["Mary Magdalene"]),
    "Mary of Bethany": ("person", ["Mary of Bethany"]),
    "Martha": ("person", ["Martha"]),
    "Lazarus of Bethany": ("person", ["Lazarus of Bethany"]),
    "David": ("person", ["King David"]),
    "Solomon": ("person", ["King Solomon"]),
    "Saul": ("person", ["King Saul"]),
    "Samuel": ("person", ["Samuel the prophet"]),
    "Elijah": ("person", ["Elijah"]),
    "Elisha": ("person", ["Elisha"]),
    "Isaiah": ("person", ["Isaiah the prophet"]),
    "Jeremiah": ("person", ["Jeremiah the prophet"]),
    "Ezekiel": ("person", ["Ezekiel the prophet"]),
    "Daniel (biblical figure)": ("person", ["Daniel the prophet"]),
    "Joshua": ("person", ["Joshua son of Nun"]),
    "Aaron": ("person", ["Aaron"]),
    "Miriam": ("person", ["Miriam"]),
    "Deborah": ("person", ["Deborah"]),
    "Ruth (biblical figure)": ("person", ["Ruth the Moabite"]),
    "Esther": ("person", ["Queen Esther"]),
    "Nehemiah": ("person", ["Nehemiah"]),
    "Ezra": ("person", ["Ezra"]),
    "Noah": ("person", ["Noah"]),
    "Adam": ("person", ["Adam"]),
    "Eve": ("person", ["Eve"]),
    "Job (biblical figure)": ("person", ["Job of Uz"]),
    "Jonah": ("person", ["Jonah"]),
    "Judas Iscariot": ("person", ["Judas Iscariot"]),
    "Jude the Apostle": ("person", ["Jude the Apostle"]),
    "James the Great": ("person", ["James son of Zebedee"]),
    "James, brother of Jesus": ("person", ["James brother of Jesus"]),
    "James, son of Alphaeus": ("person", ["James son of Alphaeus"]),
    "Matthew the Apostle": ("person", ["Matthew the Apostle"]),
    "Thomas the Apostle": ("person", ["Thomas the Apostle"]),
    "Bartholomew the Apostle": ("person", ["Bartholomew the Apostle"]),
    "Nathanael (follower of Jesus)": ("person", ["Nathanael"]),
    "Barnabas": ("person", ["Barnabas"]),
    "Silas": ("person", ["Silas"]),
    "Saint Timothy": ("person", ["Saint Timothy"]),
    "Saint Titus": ("person", ["Titus companion of Paul"]),
    "Luke the Evangelist": ("person", ["Luke the Evangelist"]),
    "Mark the Evangelist": ("person", ["Mark the Evangelist"]),
    "Philemon (biblical figure)": ("person", ["Philemon"]),
    "Pontius Pilate": ("person", ["Pontius Pilate"]),
    "Herod the Great": ("person", ["Herod the Great"]),
    "Herod Antipas": ("person", ["Herod Antipas"]),
    "Herod Agrippa": ("person", ["Herod Agrippa I"]),
    "Herod Agrippa II": ("person", ["Herod Agrippa II"]),
    "Caiaphas": ("person", ["Caiaphas"]),
    "Annas": ("person", ["Annas"]),
    "Gamaliel": ("person", ["Gamaliel"]),
    "Josephus": ("person", ["Flavius Josephus", "Josephus"]),
    "Philo": ("person", ["Philo of Alexandria"]),
    "Cyrus the Great": ("person", ["Cyrus the Great"]),
    "Nebuchadnezzar II": ("person", ["Nebuchadnezzar"]),
    "Sennacherib": ("person", ["Sennacherib"]),
    "Pharaoh": ("title", ["Pharaoh"]),
    "Pharaohs in the Bible": ("topic", ["Pharaoh of the Exodus"]),
    "Muhammad": ("person", ["Muhammad"]),
    "Pharisees": ("group", ["Pharisees"]),
    "Sadducees": ("group", ["Sadducees"]),
    "Essenes": ("group", ["Essenes"]),
    "Samaritans": ("group", ["Samaritans"]),
    "Israelites": ("group", ["Israelites"]),
    "Jews": ("group", ["Jewish people"]),
    "Early Christianity": ("topic", ["Early Christianity"]),
    "Second Temple Judaism": ("topic", ["Second Temple Judaism"]),
    "Judaism": ("religion", ["Judaism"]),
    "Christianity": ("religion", ["Christianity"]),
    "Islam": ("religion", ["Islam"]),
    "Quran": ("text", ["Quran", "Qur'an"]),
    "Torah": ("text", ["Torah"]),
    "Talmud": ("text", ["Talmud"]),
    "Mishnah": ("text", ["Mishnah"]),
    "Jerusalem Talmud": ("text", ["Jerusalem Talmud"]),
    "Midrash": ("text", ["Midrash"]),
    "Targum": ("text", ["Targum"]),
    "Antiquities of the Jews": ("text", ["Antiquities of the Jews"]),
    "The Jewish War": ("text", ["The Jewish War"]),
    "The Life of Flavius Josephus": ("text", ["Life of Josephus"]),
    "Didache": ("text", ["Didache"]),
    "1 Enoch": ("text", ["1 Enoch"]),
    "Book of Jubilees": ("text", ["Book of Jubilees"]),
    "Gospel of Thomas": ("text", ["Gospel of Thomas"]),
    "Hadith": ("text", ["Hadith"]),
    "Tafsir": ("text", ["Tafsir"]),
    "Jesus in Islam": ("topic", ["Jesus in Islam"]),
    "Moses in Islam": ("topic", ["Moses in Islam"]),
    "Abraham in Islam": ("topic", ["Abraham in Islam"]),
    "Mary in Islam": ("topic", ["Mary in Islam"]),
    "Biblical and Quranic narratives": ("topic", ["Biblical and Quranic narratives"]),
    "Christianity and Judaism": ("topic", ["Christianity and Judaism"]),
    "Christianity and Islam": ("topic", ["Christianity and Islam"]),
    "Deuterocanonical books": ("text", ["Deuterocanonical books"]),
    "Biblical canon": ("topic", ["Biblical canon"]),
    "Book of Tobit": ("text", ["Book of Tobit"]),
    "Book of Judith": ("text", ["Book of Judith"]),
    "Sirach": ("text", ["Sirach", "Ecclesiasticus"]),
    "Wisdom of Solomon": ("text", ["Wisdom of Solomon"]),
    "1 Maccabees": ("text", ["1 Maccabees"]),
    "2 Maccabees": ("text", ["2 Maccabees"]),
    "Dead Sea Scrolls": ("artifact", ["Dead Sea Scrolls"]),
    "Septuagint": ("text", ["Septuagint"]),
    "Masoretic Text": ("text", ["Masoretic Text"]),
    "Samaritan Pentateuch": ("text", ["Samaritan Pentateuch"]),
    "Ark of the Covenant": ("object", ["Ark of the Covenant"]),
    "Tabernacle": ("object", ["Tabernacle"]),
    "Menorah (Temple)": ("object", ["Temple menorah"]),
    "Mesha Stele": ("artifact", ["Mesha Stele", "Moabite Stone"]),
    "Tel Dan stele": ("artifact", ["Tel Dan stele"]),
    "Pilate stone": ("artifact", ["Pilate stone"]),
    "Siloam inscription": ("artifact", ["Siloam inscription"]),
    "Merneptah Stele": ("artifact", ["Merneptah Stele"]),
    "Cyrus Cylinder": ("artifact", ["Cyrus Cylinder"]),
    "Taylor Prism": ("artifact", ["Taylor Prism"]),
    "Lachish letters": ("artifact", ["Lachish letters"]),
    "Ketef Hinnom": ("artifact", ["Ketef Hinnom"]),
    "Deir Alla inscription": ("artifact", ["Deir Alla inscription"]),
    "Caiaphas ossuary": ("artifact", ["Caiaphas ossuary"]),
    "Delphi Inscription": ("artifact", ["Gallio Inscription"]),
    "Codex Sinaiticus": ("artifact", ["Codex Sinaiticus"]),
    "Codex Vaticanus": ("artifact", ["Codex Vaticanus"]),
    "Rylands Library Papyrus P52": ("artifact", ["Papyrus P52"]),
    "Bethsaida": ("place", ["Bethsaida"]),
    "Bethany": ("place", ["Bethany near Jerusalem"]),
    "Al-Maghtas": ("place", ["Bethany beyond the Jordan", "Al-Maghtas"]),
}


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def request_bytes(url, cache_path=None, refresh=False):
    global LAST_REQUEST
    if cache_path and cache_path.exists() and not refresh:
        return cache_path.read_bytes()
    for attempt in range(4):
        try:
            if "wikipedia.org" in url or "wikidata.org" in url:
                with NETWORK_LOCK:
                    delay = max(0, LAST_REQUEST + 1.1 - time.monotonic())
                    if delay:
                        time.sleep(delay)
                    LAST_REQUEST = time.monotonic()
            data = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=45).read()
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(data)
            return data
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 3:
                raise
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
                # Honor the service's backoff rather than bypassing rate limits.
                retry = exc.headers.get("Retry-After", "60")
                seconds = int(retry) if retry.isdigit() else 60
                with NETWORK_LOCK:
                    LAST_REQUEST = max(LAST_REQUEST, time.monotonic() + seconds)
                time.sleep(min(seconds, 60))
            else:
                time.sleep(2 ** attempt)


def api(host, params, refresh=False, cached_only=False):
    params = {**params, "format": "json", "maxlag": 5}
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    path = CACHE / "api" / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    if cached_only and not path.exists():
        return None, None
    raw = request_bytes(url, path, refresh)
    value = json.loads(raw)
    if value.get("error"):
        if value["error"].get("code") == "maxlag":
            path.unlink(missing_ok=True)
        raise ValueError(f"{host}: {value['error']}")
    return value, {"url": url, "sha256": hashlib.sha256(raw).hexdigest()}


def plain(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", value or ""))).strip()


def category(title):
    low = title.lower()
    if re.search(r"artifact|artefact|inscript|mosaic|coin|pottery|ceramic|papyr|ossuar|stele|stela|scroll|manuscript|finds|objects|material culture", low):
        return "artifacts"
    if re.search(r"archaeolog|excavat|identif|location|candidates|et-tell|al-araj|el-araj", low):
        return "archaeology"
    if re.search(r"bibl|testament|quran|qur'an|koran|talmud|josephus|literature|tradition|christian|jewish|rabbin|islam|scriptur|pilgrim|sources|reference", low):
        return "literature"
    if re.search(r"geograph|climate|topograph|hydrolog|geolog", low):
        return "geography"
    if re.search(r"histor|period|age|roman|byzantine|ottoman|hellen|medieval|antiquity|persian|israelite|bronze", low):
        return "history"
    return "overview"


class ArticleParser(HTMLParser):
    """Plain prose + source-section citation pointers; never ships HTML."""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    DROP_TAGS = {"style", "script", "table", "figure", "blockquote", "q", "math"}
    DROP_CLASSES = {"hatnote", "navbox", "vertical-navbox", "sidebar", "infobox", "toc", "mw-editsection", "reflist", "references", "noprint", "noexcerpt", "metadata", "thumb", "gallery", "sistersitebox", "authority-control", "ambox", "catlinks"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.sections = [{"title": "Overview", "anchor": "", "level": 1, "text": "", "links": [], "citationIds": [], "citationOffsets": []}]
        self.heading = None
        self.block = None
        self.link = None
        self.references = {}
        self.reference = None
        self.skip_section = False

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        parent_skip = self.stack[-1][1] if self.stack else False
        classes = set(attr.get("class", "").split())
        skip = parent_skip or tag in self.DROP_TAGS or bool(classes & self.DROP_CLASSES) or attr.get("style", "").replace(" ", "").startswith("display:none")
        if tag == "li" and attr.get("id", "").startswith("cite_note"):
            self.reference = {"id": attr["id"], "text": [], "urls": [], "depth": len(self.stack)}
            skip = True
        if self.reference and tag == "a" and attr.get("href", "").startswith(("http://", "https://", "//")):
            href = attr["href"]
            self.reference["urls"].append("https:" + href if href.startswith("//") else href)
        if tag == "a" and attr.get("href", "").startswith("#cite_note") and not self.reference:
            self.sections[-1]["citationIds"].append(attr["href"][1:])
            position = len(self.sections[-1]["text"]) + len(plain("".join(self.block["parts"]))) if self.block else len(self.sections[-1]["text"])
            self.sections[-1]["citationOffsets"].append([attr["href"][1:], position])
        if tag == "sup" and "reference" in classes:
            skip = True
        if not skip and re.fullmatch("h[2-6]", tag):
            self._flush()
            self.heading = {"tag": tag, "parts": [], "anchor": attr.get("id", ""), "level": int(tag[1])}
        if not skip and tag in {"p", "li"} and self.block is None and not self.skip_section:
            self.block = {"depth": len(self.stack), "tag": tag, "parts": []}
        if not skip and tag == "a" and self.block and self.link is None:
            href = attr.get("href", "")
            if href.startswith("/wiki/") or href.startswith("https://"):
                self.link = {"url": ("https://en.wikipedia.org" + href) if href.startswith("/") else href, "parts": []}
        if tag == "br" and self.block and not skip:
            self.block["parts"].append(" ")
        if tag not in self.VOID:
            self.stack.append((tag, skip))

    def handle_endtag(self, tag):
        # Wikimedia parse output is well-formed except optional closing tags.
        if tag in self.VOID:
            return
        i = next((i for i in range(len(self.stack)-1, -1, -1) if self.stack[i][0] == tag), -1)
        if i < 0:
            return
        skip = self.stack[i][1]
        if self.reference and tag == "li" and self.reference["depth"] == i:
            r = self.reference
            self.references[r["id"]] = {"id": r["id"], "text": plain("".join(r["text"]))[:1000], "urls": list(dict.fromkeys(r["urls"]))[:4]}
            self.reference = None
        if self.heading and tag == self.heading["tag"]:
            h = self.heading
            title = plain("".join(h["parts"]))
            self.skip_section = title.lower() in {"references", "notes", "citations", "footnotes", "external links", "see also", "bibliography", "further reading", "sources"}
            self.sections.append({"title": title, "anchor": h["anchor"], "level": h["level"], "text": "", "links": [], "citationIds": [], "citationOffsets": []})
            self.heading = None
        if tag == "a" and self.link and not skip:
            self.sections[-1]["links"].append({"label": plain("".join(self.link["parts"])), "url": self.link["url"]})
            self.link = None
        if self.block and tag == self.block["tag"] and self.block["depth"] == i:
            self._flush()
        self.stack = self.stack[:i]

    def handle_data(self, data):
        if self.reference:
            self.reference["text"].append(data)
        if self.stack and self.stack[-1][1]:
            return
        if self.heading:
            self.heading["parts"].append(data)
        elif self.block:
            self.block["parts"].append(data)
            if self.link:
                self.link["parts"].append(data)

    def _flush(self):
        if self.block:
            text = plain("".join(self.block["parts"]))
            if text:
                self.sections[-1]["text"] += ("\n\n" if self.sections[-1]["text"] else "") + text
            self.block = None


def shorten(text, maximum):
    if len(text) <= maximum:
        return text, False
    cutoff = text.rfind(" ", 0, maximum)
    return text[:cutoff if cutoff > 0 else maximum].rstrip() + " …", True


def fetch_article(title, existing, refresh=False):
    old = existing.get(title, {})
    query = {"action": "parse", "prop": "text|sections|externallinks|revid|properties"}
    cached, cached_source = api("en.wikipedia.org", {**query, "page": title, "redirects": 1}, cached_only=True) if not refresh else (None, None)
    if old.get("revision") and not refresh:
        query["oldid"] = old["revision"]
    else:
        query["page"] = title
        query["redirects"] = 1
    if cached and (not old.get("revision") or cached.get("parse", {}).get("revid") == old["revision"]):
        data, provenance = cached, cached_source
    else:
        data, provenance = api("en.wikipedia.org", query, refresh)
    parsed = data["parse"]
    properties = {p["name"]: p.get("*", "") for p in parsed.get("properties", [])}
    if "disambiguation" in properties:
        raise ValueError(f"Disambiguation page excluded: {title}")
    parser = ArticleParser()
    parser.feed(parsed["text"]["*"])
    parser._flush()
    title = parsed["title"]
    pageid, revision = parsed["pageid"], parsed["revid"]
    base_url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
    revision_url = f"https://en.wikipedia.org/w/index.php?oldid={revision}"
    raw_sections = [s for s in parser.sections if s["text"]]
    for s in raw_sections:
        s["category"] = category(s["title"])
    # Reserve space for archaeology/material/literary sections of large pages.
    maximum = 24000 if title == "Bethsaida" else 7000
    priority = sorted(range(len(raw_sections)), key=lambda n: (0 if n == 0 else (1 if raw_sections[n]["category"] in {"archaeology", "artifacts", "literature"} else 2), n))
    retained = {}
    for n in priority:
        s = raw_sections[n]
        if maximum < 240:
            continue
        limit = min(maximum, 5000 if title == "Bethsaida" else 1400)
        text, truncated = shorten(s["text"], limit)
        maximum -= len(text)
        ids = list(dict.fromkeys(cid for cid, position in s["citationOffsets"] if position <= len(text)))
        retained[n] = {**s, "text": text, "truncated": truncated, "citationIds": ids, "url": revision_url + ("#" + urllib.parse.quote(s["anchor"]) if s["anchor"] else "")}
        retained[n].pop("citationOffsets")
        retained[n]["links"] = list({v["url"]: v for v in s["links"] if v["label"] and "wikipedia.org/" not in v["url"]}.values())[:3]
    sections = [retained[n] for n in sorted(retained)]
    citation_ids = {c for s in sections for c in s["citationIds"]}
    refs = [{"id": k, "text": shorten(v["text"], 120)[0], "url": revision_url + "#" + k} for k, v in parser.references.items() if k in citation_ids]
    summary = shorten(raw_sections[0]["text"] if raw_sections else "", 500)[0]
    fetched = old.get("retrievedAt") if old.get("revision") == revision else None
    return {
        "id": f"wp-{pageid}", "title": title, "summary": summary, "sections": sections,
        "url": base_url, "revision": revision, "revisionUrl": revision_url,
        "historyUrl": f"https://en.wikipedia.org/w/index.php?title={urllib.parse.quote(title.replace(' ', '_'))}&action=history",
        "license": "CC BY-SA 4.0", "licenseUrl": WIKI_LICENSE,
        "attribution": "Wikipedia contributors", "retrievedAt": fetched or utcnow(),
        "source": provenance, "references": refs,
        "externalReferences": list(dict.fromkeys(u for u in parsed.get("externallinks", []) if u.startswith(("http://", "https://")) and len(u) < 500))[:8],
        "abridged": len(retained) < len(raw_sections) or any(s["truncated"] for s in sections),
        "sourceSectionCount": len(raw_sections),
        "modifications": "Converted to plain text; infoboxes, tables, images, block quotations, navigation and reference-only sections omitted. Long sections abridged. Section categories added automatically, not expert-reviewed.",
    }


def build_geography(ancient, modern):
    modern = {v["id"]: v for v in modern}
    places, chapters, verses = {}, {}, {}
    for item in ancient:
        candidates, seen = [], set()
        unknown = set()
        for identification in item.get("identifications", []):
            for resolution in identification.get("resolutions", []):
                if "lonlat" not in resolution:
                    unknown.add(resolution.get("special", identification.get("special", "unknown_place")))
                    continue
                lon, lat = map(float, resolution["lonlat"].split(","))
                mid = resolution.get("modern_basis_id", "")
                label = plain(resolution.get("description")) or modern.get(mid, {}).get("friendly_id", item["friendly_id"])
                key = (lon, lat, label)
                if key in seen:
                    continue
                seen.add(key)
                score = item.get("modern_associations", {}).get(mid, {}).get("score", identification.get("score", {}).get("time_total", 0))
                candidates.append({
                    "id": mid or f"{item['id']}-{len(candidates)}",
                    "name": modern.get(mid, {}).get("friendly_id", label),
                    "lon": lon, "lat": lat, "kind": resolution.get("type", ""),
                    "precision": resolution.get("lonlat_type", "point"),
                    "score": score, "description": label,
                    "radiusMeters": identification.get("geometry_radius_meters"),
                })
                coordinate_source = modern.get(mid, {}).get("coordinates_source", {})
                if coordinate_source.get("type") == "osm":
                    candidates[-1]["coordinateSourceUrl"] = coordinate_source.get("url", "https://www.openstreetmap.org/")
                    candidates[-1]["coordinateAttribution"] = "© OpenStreetMap contributors"
                    candidates[-1]["coordinateLicense"] = "ODbL 1.0"
        candidates.sort(key=lambda c: -c["score"])
        refs = []
        for v in item.get("verses", []):
            sort = str(v["sort"]).zfill(8)
            ref = f"{int(sort[:2])}.{int(sort[2:5])}.{int(sort[5:])}"
            refs.append(ref)
            chapter_key = ".".join(ref.split(".")[:2])
            chapters.setdefault(chapter_key, []).append(item["id"])
            verses.setdefault(ref, []).append(item["id"])
        names = sorted(item.get("translation_name_counts", {}), key=lambda n: -item["translation_name_counts"][n])
        places[item["id"]] = {
            "id": item["id"], "name": names[0] if names else item["friendly_id"],
            "disambiguatedName": item["friendly_id"], "aliases": names,
            "types": item.get("types", []), "refs": refs,
            "url": "https://www.openbible.info/geo/ancient/" + item["url_slug"],
            "comment": item.get("comment", ""), "candidates": candidates,
            "status": "unlocated" if not candidates else ("disputed" if len(candidates) > 1 or unknown else ("high confidence in source" if candidates[0]["score"] >= 1000 else "tentative")),
            "unlocatedReasons": sorted(unknown),
            "bibliographyIds": list(item.get("identification_sources", {})),
        }
    return {"places": places, "chapters": {k: list(dict.fromkeys(v)) for k, v in chapters.items()}, "verses": {k: list(dict.fromkeys(v)) for k, v in verses.items()}}


def linked_titles(ancient, refresh):
    by_title, by_qid = {}, {}
    for item in ancient:
        linked = item.get("linked_data", {})
        if "s7cc8b2" in linked:
            by_qid.setdefault(linked["s7cc8b2"]["id"], []).append(item["id"])
        if "sf42caf" in linked:
            link = linked["sf42caf"]
            url = link.get("url", "")
            title = urllib.parse.unquote(url.split("/wiki/")[-1]).replace("_", " ") if "/wiki/" in url else link.get("title", "")
            if title:
                by_title.setdefault(title, set()).add(item["id"])
    ids = sorted(by_qid)
    for start in range(0, len(ids), 40):
        data, _ = api("www.wikidata.org", {"action": "wbgetentities", "ids": "|".join(ids[start:start+40]), "props": "sitelinks", "sitefilter": "enwiki"}, refresh)
        for qid, entity in data["entities"].items():
            title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
            if title:
                by_title.setdefault(title, set()).update(by_qid[qid])
    # Both OpenBible disambiguated Bethsaidas share the modern scholarly article.
    for item in ancient:
        if item["friendly_id"].startswith("Bethsaida"):
            by_title.setdefault("Bethsaida", set()).add(item["id"])
    return by_title


def bethsaida_notes():
    return {
        "title": "Bethsaida: evidence and competing identifications",
        "status": "Disputed identification; map markers are candidates, not a settled location.",
        "reviewedAt": utcnow()[:10],
        "license": "CC BY 4.0", "licenseUrl": GEO_LICENSE,
        "notes": [
            {"category": "archaeology", "title": "Et-Tell candidate",
             "text": "Rami Arav's Bethsaida Excavations Project identifies et-Tell with Bethsaida. Its overview reports Hellenistic and Roman occupation above an Iron Age fortified settlement. The site lies inland from today's lakeshore; the project argues that shoreline change helps explain the distance.",
             "sourceTitle": "Bethsaida Excavations Project, Bethsaida Overview (2017)",
             "url": "https://bethsaidaarchaeology.org/2017/01/05/bethsaida-overview/",
             "sourceType": "excavation project account", "position": "supports et-Tell"},
            {"category": "artifacts", "title": "Fishing implements at et-Tell",
             "text": "The et-Tell project reports net weights, hooks, anchors and line sinkers among its finds. These objects inform arguments about fishing activity; they do not independently establish the site's ancient name.",
             "sourceTitle": "Bethsaida Excavations Project, Bethsaida Overview (2017)",
             "url": "https://bethsaidaarchaeology.org/2017/01/05/bethsaida-overview/",
             "sourceType": "excavation project account", "position": "supports et-Tell"},
            {"category": "archaeology", "title": "El-Araj candidate",
             "text": "The el-Araj project's first-season report records early Roman pottery and later Byzantine and early Islamic remains. Its excavators interpret the early Roman material as evidence that el-Araj remains a candidate for Bethsaida.",
             "sourceTitle": "El Araj Excavation Project, Season 1 Report",
             "url": "https://www.bethsaida-julias.com/season1report",
             "sourceType": "excavation project report", "position": "supports el-Araj"},
            {"category": "artifacts", "title": "A Byzantine mosaic invoking Peter",
             "text": "In 2022 the el-Araj excavation team announced a Greek mosaic inscription naming a donor and invoking Peter's intercession. The team interprets it as evidence for the basilica's association with Peter. A Byzantine commemoration is later evidence of a tradition, not direct proof of a first-century house.",
             "sourceTitle": "El Araj Excavation Project, 2022 inscription announcement",
             "url": "https://www.bethsaida-julias.com/home",
             "sourceType": "excavation project announcement", "position": "supports el-Araj"},
            {"category": "archaeology", "title": "The 2024 el-Araj season",
             "text": "The team's 2024 report describes a wall with pottery and a coin assigned to the Hasmonean period. It also reports earlier walls near the church whose interpretation remains provisional; an early Christian sacred complex is the excavators' hypothesis, not an established identification of an apostle's house.",
             "sourceTitle": "El Araj Excavation Project, Season 8 Report (2024)",
             "url": "https://www.bethsaida-julias.com/season8report",
             "sourceType": "excavation project report", "position": "supports el-Araj; preliminary interpretation"},
            {"category": "literature", "title": "Josephus and the pilgrim tradition",
             "text": "The el-Araj project relates its finds to Josephus, Antiquities 18.28, on Bethsaida's promotion as Julias, and to Willibald's eighth-century account of a church commemorating Peter and Andrew. These written witnesses differ in date and purpose from the Gospel narratives.",
             "sourceTitle": "El Araj Excavation Project, historical background to the inscription announcement",
             "url": "https://www.bethsaida-julias.com/home",
             "sourceType": "excavators discussing ancient literary sources", "position": "supports el-Araj"},
        ],
        "scope": "A focused comparison of two excavation teams' published claims. It is not an independent adjudication, a catalog of all finds, or an exhaustive bibliography. OpenBible also records historical proposals at El Mess'adiyye and Tabgha.",
    }


def validate_corpus():
    """Check data integrity and disputed locations independently of rendering."""
    geo = json.loads((GEO / "index.json").read_text())
    encyclopedia = json.loads((ENC / "index.json").read_text())
    ids = {a["id"] for a in encyclopedia["articles"]}
    for key, place_ids in geo["chapters"].items():
        assert len(place_ids) == len(set(place_ids)), f"Duplicate chapter association: {key}"
        for pid in place_ids:
            assert any(r.startswith(key + ".") for r in geo["places"][pid]["refs"]), key
    for ref, place_ids in geo["verses"].items():
        b, c, v = map(int, ref.split("."))
        assert 1 <= b <= 66 and c > 0 and v > 0, ref
        for pid in place_ids:
            assert ref in geo["places"][pid]["refs"], (ref, pid)
    for place in geo["places"].values():
        if "articleId" in place:
            assert place["articleId"] in ids
        for candidate in place["candidates"]:
            assert all(math.isfinite(candidate[k]) for k in ("lon", "lat"))
            assert -180 <= candidate["lon"] <= 180 and -90 <= candidate["lat"] <= 90
        if not place["candidates"]:
            assert place["status"] == "unlocated"
    bethsaida = [p for p in geo["places"].values() if "43.1.44" in p["refs"] and p["name"] == "Bethsaida"]
    assert bethsaida, "John 1:44 must retain its Bethsaida association"
    assert bethsaida[0]["status"] == "disputed"
    assert {"m1ec77e", "m00b3ac"} <= {c["id"] for c in bethsaida[0]["candidates"]}, "Both et-Tell and el-Araj must remain"
    for meta in encyclopedia["articles"]:
        article = json.loads((ENC / "articles" / (meta["id"] + ".json")).read_text())
        assert article["revision"] and str(article["revision"]) in article["revisionUrl"]
        assert article["license"] == "CC BY-SA 4.0" and article["historyUrl"]
        assert article["source"]["sha256"] and article["sections"] and article["summary"]
        assert all(s["url"].startswith(article["revisionUrl"]) for s in article["sections"])
        if article["category"] in {"person", "title"}:
            assert article["autoLink"] is False, f"Ambiguous person match: {article['title']}"
    size = sum(p.stat().st_size for d in (GEO, ENC) for p in d.rglob("*") if p.is_file())
    assert size <= 12 * 1024 * 1024, "Corpus exceeds 12 MiB publication budget"
    return {"places": len(geo["places"]), "articles": len(ids), "expandedMiB": round(size / 1024 / 1024, 2)}


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--refresh", action="store_true")
    args.add_argument("--verify-only", action="store_true")
    args.add_argument("--limit", type=int, default=0, help="Maximum geographic Wikipedia titles; 0 means all linked titles.")
    args.add_argument("--workers", type=int, default=4)
    args = args.parse_args()
    if args.verify_only:
        print(json.dumps(validate_corpus(), indent=2))
        return
    for directory in (CACHE, GEO, ENC / "articles", LICENSES):
        directory.mkdir(parents=True, exist_ok=True)
    inputs = {}
    for name, expected in HASHES.items():
        url = f"{RAW}/data/{name}.jsonl"
        raw = request_bytes(url, CACHE / f"{name}.jsonl")
        assert hashlib.sha256(raw).hexdigest() == expected, f"Source hash mismatch: {name}"
        inputs[name] = [json.loads(line) for line in raw.splitlines()]
    geo = build_geography(inputs["ancient"], inputs["modern"])
    old_index = json.loads((ENC / "index.json").read_text()) if (ENC / "index.json").exists() else {}
    existing = {
        title: a for a in old_index.get("articles", [])
        for title in [a["title"], *a.get("sourceTitles", [])]
    }
    print("Resolving linked Wikipedia titles…", flush=True)
    title_places = (
        {title: set(ids) for title, ids in old_index["geographyTitleMap"].items()}
        if old_index.get("geographyTitleMap") and not args.refresh
        else linked_titles(inputs["ancient"], args.refresh)
    )
    geo_titles = sorted(title_places)
    if args.limit:
        geo_titles = geo_titles[:args.limit]
    targets = sorted(set(geo_titles) | set(SEEDS))
    print(f"Importing {len(targets)} Wikipedia titles, with revision pinning…", flush=True)
    articles, failures = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(fetch_article, title, existing, args.refresh): title for title in targets}
        for count, future in enumerate(concurrent.futures.as_completed(pending), 1):
            title = pending[future]
            try:
                article = future.result()
                if not article["summary"]:
                    raise ValueError("No reusable prose found")
                aid = article["id"]
                kind, aliases = SEEDS.get(title, ("place", []))
                place_ids = title_places.get(title, set())
                article["category"] = kind
                article["aliases"] = list(dict.fromkeys([article["title"], *aliases]))
                article["sourceTitles"] = [title]
                article["autoLink"] = kind not in {"person", "title"} and not (title in {"Bethany", "Tabernacle"})
                article["relatedPlaces"] = sorted(place_ids)
                if aid in articles:
                    previous = articles[aid]
                    article["relatedPlaces"] = sorted(set(previous["relatedPlaces"] + article["relatedPlaces"]))
                    article["aliases"] = list(dict.fromkeys(previous["aliases"] + article["aliases"]))
                    article["sourceTitles"] = sorted(set(previous.get("sourceTitles", []) + article["sourceTitles"]))
                    if previous["category"] != "place":
                        article["category"] = previous["category"]
                article["autoLink"] = article["category"] not in {"person", "title"} and article["title"] not in {"Bethany", "Tabernacle"}
                articles[aid] = article
                if article["title"] == "Bethsaida":
                    article["studyNotes"] = bethsaida_notes()
                    article["notes"] = article["studyNotes"]["notes"]
            except Exception as exc:
                failures.append({"title": title, "error": str(exc)})
            if count % 25 == 0 or count == len(targets):
                print(f"  {count}/{len(targets)} processed; {len(articles)} articles; {len(failures)} omitted", flush=True)
    for aid, article in articles.items():
        for pid in article["relatedPlaces"]:
            geo["places"][pid]["articleId"] = aid
        write_json(ENC / "articles" / f"{aid}.json", article)
    # Remove obsolete generated article files, never user-authored files.
    for path in (ENC / "articles").glob("wp-*.json"):
        if path.stem not in articles:
            path.unlink()
    geographic_articles = sum(bool(a["relatedPlaces"]) for a in articles.values())
    people_articles = sum(a["category"] == "person" for a in articles.values())
    meta = {
        "title": "Biblical geography", "attribution": "OpenBible.info", "license": "CC BY 4.0", "licenseUrl": GEO_LICENSE,
        "source": REPO, "commit": COMMIT, "retrievedAt": utcnow(),
        "sourceFiles": {n: {"url": f"{RAW}/data/{n}.jsonl", "sha256": h} for n, h in HASHES.items()},
        "placeCount": len(geo["places"]), "candidateCount": sum(len(p["candidates"]) for p in geo["places"].values()),
        "chapterCount": len(geo["chapters"]), "verseCount": len(geo["verses"]),
        "unlocatedCount": sum(not p["candidates"] for p in geo["places"].values()),
        "withArticles": sum("articleId" in p for p in geo["places"].values()),
        "scope": "Every entry in the pinned OpenBible Protestant-Bible geocoding dataset. Associations can reflect translation variants. Deuterocanonical books are outside this source's scope. Unlocated places are retained without invented coordinates.",
        "precisionNote": "Points may represent a settlement, region, river or approximate area. All source candidates are preserved. Coordinates are reference points, not ancient boundary reconstructions or travel routes.",
        "scoreNote": "Historical OpenBible source-weighted score (roughly through 2020); not a calibrated probability, current archaeological consensus or an endorsement. Newer findings can change assessments.",
        "modifications": "Normalized verse IDs and names; flattened alternative resolutions; generated passage indices; original bibliography retained separately. Geometry and images not imported.",
        "additionalAttribution": "Source coordinates marked as OpenStreetMap retain © OpenStreetMap contributors attribution and ODbL 1.0 terms.",
        "additionalLicenseUrl": "https://www.openstreetmap.org/copyright",
    }
    geo["meta"] = meta
    write_json(GEO / "index.json", geo)
    bibliography = {
        r["id"]: {k: r[k] for k in ["display_name", "contributors", "year", "url", "worldcat_url", "google_books_url", "friendly_id", "type"] if k in r}
        for r in inputs["source"]
    }
    write_json(GEO / "bibliography.json", bibliography)
    article_list = []
    for article in sorted(articles.values(), key=lambda a: a["title"].casefold()):
        entry = {k: article[k] for k in ["id", "title", "summary", "category", "aliases", "autoLink", "sourceTitles", "relatedPlaces", "url", "revision", "revisionUrl", "historyUrl", "license", "licenseUrl", "retrievedAt", "abridged"]}
        entry["categories"] = sorted(set(s["category"] for s in article["sections"]))
        entry["path"] = f"/data/encyclopedia/articles/{article['id']}.json"
        article_list.append(entry)
    index = {
        "meta": {
            "title": "Study encyclopedia", "attribution": "Wikipedia contributors", "license": "CC BY-SA 4.0", "licenseUrl": WIKI_LICENSE,
            "generatedAt": utcnow(), "articleCount": len(articles), "geographicArticleCount": geographic_articles, "personArticleCount": people_articles,
            "requestedTitles": len(targets), "failedTitles": len(failures), "geographicTitlesAvailable": len(title_places),
            "coverage": "A broad imported reference corpus linked from OpenBible, plus a named-entity and artifact seed list. Abridged Wikipedia prose with revision-level attribution; not exhaustive, independently verified, or a substitute for primary scholarship.",
            "citationNote": "Wikipedia footnotes are retained as bibliographic pointers. They are not automatically verified endorsements of every nearby claim. Automatically assigned section categories may be incomplete.",
            "trainingNote": "Useful as attributed retrieval context. Training, redistribution and derived datasets must retain applicable license/attribution obligations. No trained language model is included in this corpus.",
            "omissions": "Images, infoboxes, tables, block quotations, navigation and reference-only sections omitted. Long articles are abridged. No copyrighted third-party article bodies downloaded.",
        }, "articles": article_list, "failures": failures,
        "geographyTitleMap": {title: sorted(place_ids) for title, place_ids in sorted(title_places.items())},
    }
    write_json(ENC / "index.json", index)
    LICENSES.joinpath("geography-openbible.txt").write_bytes(request_bytes(f"{RAW}/license.txt", CACHE / "license.txt"))
    LICENSES.joinpath("geography-openstreetmap.txt").write_text(
        "Some point coordinates in the OpenBible source identify OpenStreetMap as their origin.\n"
        "Those candidates retain coordinateSourceUrl, coordinateAttribution and coordinateLicense.\n"
        "© OpenStreetMap contributors. Open Database License (ODbL) 1.0.\n"
        "Attribution and license: https://www.openstreetmap.org/copyright\n"
        "Legal code: https://opendatacommons.org/licenses/odbl/1-0/\n"
        "No OpenStreetMap polygon/path geometry, tiles or images are included in this corpus.\n"
    )
    LICENSES.joinpath("encyclopedia-wikipedia.txt").write_text(
        "Study encyclopedia text © Wikipedia contributors.\n"
        "CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/\n"
        "Legal code: https://creativecommons.org/licenses/by-sa/4.0/legalcode.en\n\n"
        "Each article includes its source URL, stable revision URL, author-history URL and retrieval date.\n"
        "Modified: HTML converted to plain text; selected sections abridged; infoboxes, tables, images,\n"
        "block quotations and navigation omitted; section categories and links added.\n"
        "These adapted article texts are distributed under CC BY-SA 4.0.\n"
        "Bibliographic links do not license the third-party works to which they point.\n"
        "Bethsaida study notes are separately identified as original summaries licensed CC BY 4.0.\n"
        "See https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content\n"
    )
    size = sum(p.stat().st_size for d in (GEO, ENC) for p in d.rglob("*") if p.is_file())
    print(json.dumps({**meta, "articles": len(articles), "expandedMiB": round(size / 1024 / 1024, 2), "failures": failures}, indent=2))
    if size > 12 * 1024 * 1024:
        raise SystemExit("Corpus exceeds the 12 MiB publication budget; reduce per-article text limits before publishing.")
    print("Integrity checks passed:", validate_corpus())


if __name__ == "__main__":
    main()
