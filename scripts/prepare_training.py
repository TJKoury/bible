#!/usr/bin/env python3
"""Export source-disjoint continued-pretraining data. Does not train a model.

Output defaults outside public/. These are historical passages, not vetted
answers, preference labels, or an instruction-tuning corpus.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/training/research-v1")
    parser.add_argument("--seed", default="scripture-research-v1")
    parser.add_argument("--equalize-traditions", action="store_true",
                        help="Downsample each religion to equal passage counts within each split. No doctrinal ranking.")
    args = parser.parse_args()
    manifest_path = ROOT / "public/data/research/manifest.json"
    chunks_path = ROOT / "public/data/research/chunks.json"
    manifest = json.loads(manifest_path.read_text())
    chunks = json.loads(chunks_path.read_text())
    sources = {s["id"]: s for s in manifest["sources"]}
    by_tradition = defaultdict(list)
    for source in sources.values():
        if source.get("trainingEligible"):
            by_tradition[source["tradition"]].append(source["id"])
    assignments = {}
    for tradition, ids in sorted(by_tradition.items()):
        ids.sort(key=lambda sid: hashlib.sha256(f"{args.seed}:{sid}".encode()).hexdigest())
        if len(ids) < 3:
            raise ValueError(f"Need at least three separate source documents for {tradition}")
        for i, sid in enumerate(ids):
            assignments[sid] = "test" if i == 0 else "valid" if i == 1 else "train"
    out = args.output.resolve()
    if out == (ROOT / "public") or ROOT / "public" in out.parents:
        raise ValueError("Training exports must stay outside public/ to avoid duplicating the reading corpus.")
    out.mkdir(parents=True, exist_ok=True)
    stats = {}
    used = {}
    for split in ("train", "valid", "test"):
        records = [c for c in chunks if assignments.get(c["sourceId"]) == split]
        if args.equalize_traditions:
            groups = defaultdict(list)
            for record in records:
                groups[sources[record["sourceId"]]["tradition"]].append(record)
            cap = min(len(group) for group in groups.values())
            records = []
            for tradition, group in sorted(groups.items()):
                random.Random(f"{args.seed}:{split}:{tradition}").shuffle(group)
                records.extend(group[:cap])
            records.sort(key=lambda c: (c["sourceId"], c["ordinal"]))
        used[split] = {r["sourceId"] for r in records}
        with (out / f"{split}.jsonl").open("w") as train, (out / f"{split}.provenance.jsonl").open("w") as provenance:
            for record in records:
                # A plain text field is understood by common continued-training loaders.
                # Attribution is retained separately; no invented question or desired answer.
                train.write(json.dumps({"text": record["text"]}, ensure_ascii=False) + "\n")
                provenance.write(json.dumps({
                    "id": record["id"], "sourceId": record["sourceId"],
                    "locator": record["locator"], "textSha256": hashlib.sha256(record["text"].encode()).hexdigest(),
                    "sourceSha256": sources[record["sourceId"]]["sha256"],
                }, ensure_ascii=False) + "\n")
        stats[split] = dict(passages=len(records),
                           words=sum(len(r["text"].split()) for r in records),
                           sources=sorted(used[split]),
                           religionCounts=dict(Counter(sources[r["sourceId"]]["tradition"] for r in records)),
                           sha256=hash_file(out / f"{split}.jsonl"))
    assert not (used["train"] & used["valid"] or used["train"] & used["test"] or used["valid"] & used["test"])
    rights = dict(
        purpose="Continued-pretraining candidate texts; not a reviewed instruction-tuning dataset.",
        seed=args.seed, splitUnit="source document (all passages from a work stay together)",
        equalizedPassageCounts=args.equalize_traditions, splits=stats,
        sourceManifestSha256=hash_file(manifest_path), chunksSha256=hash_file(chunks_path),
        sources=[{**s, "split": assignments.get(s["id"])} for s in sources.values()],
        excluded=["Modern journal full texts", "Study dossiers and generated summaries", "Synthetic theological Q&A"],
        limitations=[
            "Source separation reduces same-document leakage; shared scriptural quotations and intellectual influence may still cross splits.",
            "Perplexity on held-out documents does not measure theological accuracy, fair comparison, or citation reliability.",
            "Equal passage counts do not make the collection representative of all religious schools.",
            "Historical polemics, quotations, objections and editorial notes need role annotations before supervised answer training.",
            "No weights are produced. A selected base model, tokenizer, training run, evaluation and WebGPU export are separate work.",
            "PD status is for the USA; a model's licensing and the deployment jurisdiction also require review.",
        ])
    (out / "rights-and-splits.json").write_text(json.dumps(rights, ensure_ascii=False, indent=2) + "\n")
    for split, stat in stats.items():
        print(f"{split}: {stat['passages']:,} passages, {len(stat['sources'])} source documents, {stat['religionCounts']}")
    print(f"Exported to {out}; no model trained.")


if __name__ == "__main__":
    main()
