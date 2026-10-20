#!/usr/bin/env python3
"""Build an exhaustive place registry, without inventing reconstruction coverage.

Reads the pinned local geography/encyclopedia indexes and curated study JSON.
No network access. Run from any directory:
    python3 scripts/build_reconstructions.py
    python3 scripts/build_reconstructions.py --verify-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data"
OUTPUT = DATA / "reconstructions" / "index.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_study(study: dict, places: dict) -> None:
    assert study["placeIds"], f'{study["id"]}: missing place IDs'
    assert set(study["placeIds"]) <= places.keys(), "Unknown place ID"
    periods = {item["id"] for item in study.get("periods", [])}
    sources = {item["id"] for item in study.get("sources", [])}
    sites = {item["id"] for item in study.get("sites", [])}
    claims = {item["id"] for item in study.get("claims", [])}
    water = {item["id"] for item in study.get("waterLevelAlternatives", [])}
    for item in study.get("periods", []):
        assert set(item.get("claimIds", [])) <= claims
        assert set(item.get("waterLevelAlternativeIds", [])) <= water
    for item in study.get("claims", []):
        assert set(item["periodIds"]) <= periods
        assert set(item["siteIds"]) <= sites
        assert set(item["sourceIds"]) <= sources
    for item in study.get("sites", []):
        assert set(item["periodIds"]) <= periods
        assert set(item["claimIds"]) <= claims
        assert item["coordinateSource"] in sources
        assert set(item["placeIds"]) <= places.keys()
        if item.get("candidateId"):
            for place_id in item["placeIds"]:
                candidate = next(
                    c for c in places[place_id]["candidates"]
                    if c["id"] == item["candidateId"]
                )
                assert item["geometry"] == {
                    "type": "Point",
                    "coordinates": [candidate["lon"], candidate["lat"]],
                }, "Study point differs from its attributed reference coordinate"
    for item in study.get("waterLevelAlternatives", []):
        assert set(item["periodIds"]) <= periods
        assert set(item["claimIds"]) <= claims
        assert item["sourceId"] in sources
        assert item["kind"] in {"interval", "upper-bound", "find-elevation"}
        if item["kind"] == "find-elevation":
            assert not item["allowIllustrativeHeightScreen"]
        if item.get("geometry") is None:
            assert not item["renderAsWaterSurface"]


def build() -> dict:
    geography_path = DATA / "geography" / "index.json"
    encyclopedia_path = DATA / "encyclopedia" / "index.json"
    geography = read_json(geography_path)
    encyclopedia = read_json(encyclopedia_path)
    articles = {article["id"]: article for article in encyclopedia["articles"]}
    studies = []
    study_ids_by_place: dict[str, list[str]] = {
        place_id: [] for place_id in geography["places"]
    }
    study_paths = sorted((DATA / "reconstructions").glob("*.json"))
    for path in study_paths:
        if path.name == "index.json":
            continue
        study = read_json(path)
        # Only study files participate; other manifests may share this directory.
        if "placeIds" not in study or "periods" not in study:
            continue
        validate_study(study, geography["places"])
        studies.append({
            "id": study["id"],
            "title": study["title"],
            "path": f"/data/reconstructions/{path.name}",
            "placeIds": study["placeIds"],
            "status": study["status"],
            "periodIds": [period["id"] for period in study["periods"]],
            "sha256": digest(path),
        })
        for place_id in study["placeIds"]:
            study_ids_by_place[place_id].append(study["id"])

    places = {}
    for place_id, place in sorted(geography["places"].items()):
        article = articles.get(place.get("articleId"))
        candidates = []
        for candidate in place["candidates"]:
            candidates.append({
                "id": candidate["id"],
                "name": candidate["name"],
                "geometry": {
                    "type": "Point",
                    "coordinates": [candidate["lon"], candidate["lat"]],
                },
                "kind": candidate["kind"],
                "precision": candidate["precision"],
                "horizontalAccuracyMeters": None,
                "sourceRadiusMeters": candidate["radiusMeters"],
                "sourceScore": candidate["score"],
                "sourceUrl": candidate.get("coordinateSourceUrl", place["url"]),
                "attribution": candidate.get(
                    "coordinateAttribution", "OpenBible.info"
                ),
                "license": candidate.get("coordinateLicense", "CC BY 4.0"),
                "ancientGeometry": False,
            })
        study_ids = study_ids_by_place[place_id]
        places[place_id] = {
            "id": place_id,
            "name": place["name"],
            "disambiguatedName": place["disambiguatedName"],
            "studyIds": study_ids,
            "coverage": (
                "dated-evidence-only" if study_ids
                else "reference-points-only" if candidates
                else "unlocated"
            ),
            "coverageLabel": (
                "Dated evidence; no ancient reconstruction geometry"
                if study_ids else "No dated reconstruction geometry"
            ),
            "hasDatedGeometry": False,
            "hasAncientTerrain": False,
            "candidateStatus": place["status"],
            "candidateCount": len(candidates),
            "candidates": candidates,
            "provenanceUrl": place["url"],
            "geographyPath": "/data/geography/index.json",
            "encyclopedia": {
                key: article[key] for key in [
                    "id", "title", "path", "url", "revisionUrl", "historyUrl",
                    "license", "licenseUrl",
                ]
            } if article else None,
            "externalSourceIds": (
                ["corinth-ascsa-gis"] if place_id == "a6f437a" else []
            ),
        }

    return {
        "meta": {
            "schemaVersion": 1,
            "title": "Landscape evidence coverage",
            "scope": "Every place in the current pinned geography corpus; reconstruction evidence is added independently for each place.",
            "placeCount": len(places),
            "candidateCount": sum(p["candidateCount"] for p in places.values()),
            "studyCount": len(studies),
            "placesWithStudies": sum(bool(p["studyIds"]) for p in places.values()),
            "placesWithDatedGeometry": 0,
            "placesWithEncyclopedia": sum(p["encyclopedia"] is not None for p in places.values()),
            "unlocatedCount": sum(not p["candidateCount"] for p in places.values()),
            "geometryNote": "All candidate coordinates are modern reference points. A point may represent a region or river; it is not an ancient footprint, shoreline, route or dated occupation assertion.",
            "scoreNote": geography["meta"]["scoreNote"],
            "corpusScope": geography["meta"]["scope"],
            "generation": "Deterministic local build; no network calls or inferred ancient geometry.",
            "sourceFiles": {
                "geography": {
                    "path": "/data/geography/index.json",
                    "sha256": digest(geography_path),
                    "retrievedAt": geography["meta"]["retrievedAt"],
                    "upstreamCommit": geography["meta"]["commit"],
                },
                "encyclopedia": {
                    "path": "/data/encyclopedia/index.json",
                    "sha256": digest(encyclopedia_path),
                },
            },
            "attribution": geography["meta"]["attribution"],
            "license": geography["meta"]["license"],
            "licenseUrl": geography["meta"]["licenseUrl"],
            "additionalAttribution": geography["meta"]["additionalAttribution"],
            "additionalLicenseUrl": geography["meta"]["additionalLicenseUrl"],
            "encyclopediaNote": "Article pointers retain revision, contributor-history and CC BY-SA attribution. No Wikipedia article prose is duplicated here.",
        },
        "places": places,
        "studies": studies,
        "externalSources": [{
            "id": "corinth-ascsa-gis",
            "title": "Corinth archaeological data and basemaps",
            "author": "James Herbst / American School of Classical Studies at Athens",
            "url": "https://www.ascsa.org/excavations/ancient-corinth/digital-corinth/maps-gis-data-and-archaeological-data-for-corinth-and-greece",
            "placeIds": ["a6f437a"],
            "license": "CC BY-SA 4.0 for the credited Corinth archaeological data and basemaps; inspect individual redistributed layer terms",
            "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0/",
            "reviewedAt": "2026-10-20",
            "status": "external-data-lead-not-imported",
            "note": "The official portal advertises GIS data and archaeological layers. No geometry, construction date or accuracy was imported or inferred.",
        }],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.verify_only:
        assert read_json(OUTPUT) == result, "Registry is stale; regenerate it"
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        key: result["meta"][key] for key in [
            "placeCount", "candidateCount", "studyCount", "placesWithStudies",
            "placesWithDatedGeometry", "placesWithEncyclopedia", "unlocatedCount",
        ]
    }))


if __name__ == "__main__":
    main()
