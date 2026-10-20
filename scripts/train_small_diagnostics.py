#!/usr/bin/env python3
"""Measure held-out loss by represented religion and after requantization."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from train_model import validate_dataset

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / ".cache/training/qwen3-0.6b-v2")
    args = parser.parse_args()
    experiment = args.experiment.resolve()
    data = ROOT / ".cache/training/research-v1"
    validate_dataset(data)
    rights = json.loads((data / "rights-and-splits.json").read_text())
    sources = {s["id"]: s for s in rights["sources"]}
    rows = [json.loads(line) for line in (data / "test.jsonl").read_text().splitlines()]
    proofs = [json.loads(line) for line in (data / "test.provenance.jsonl").read_text().splitlines()]
    result = {
        "scope": "Language modeling on held-out source documents; not religious accuracy or fairness scores.",
        "limit": "One held-out source per religion; historical English texts; at most1024 tokens per record.",
        "rightsManifestSha256": hashlib.sha256((data / "rights-and-splits.json").read_bytes()).hexdigest(),
        "results": [],
    }
    for religion in ("Christianity", "Judaism", "Islam"):
        directory = experiment / "diagnostics" / religion.lower()
        directory.mkdir(parents=True, exist_ok=True)
        pairs = [(row, proof) for row, proof in zip(rows, proofs)
                 if sources[proof["sourceId"]]["tradition"] == religion]
        (directory / "test.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row, _ in pairs))
        (directory / "test.provenance.jsonl").write_text(
            "".join(json.dumps(proof, ensure_ascii=False) + "\n" for _, proof in pairs))
        for variant, model, adapter in (
            ("base", ROOT / ".cache/models/qwen3-0.6b-mlx-4bit", ""),
            ("adapter", ROOT / ".cache/models/qwen3-0.6b-mlx-4bit", str(experiment / "adapters")),
            ("requantized", experiment / "fused-mlx-4bit", ""),
        ):
            log_path = directory / f"{variant}.log"
            command = [sys.executable, "-m", "mlx_lm", "lora", "--model", str(model),
                       "--data", str(directory), "--test", "--test-batches", "-1",
                       "--batch-size", "1", "--max-seq-length", "1024",
                       "--seed", "17", "--adapter-path", adapter]
            with log_path.open("w") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
            match = re.search(r"Test loss ([0-9]+\.[0-9]+), Test ppl ([0-9]+\.[0-9]+)",
                              log_path.read_text())
            if not match:
                raise ValueError(f"No loss in {log_path}")
            result["results"].append({
                "religion": religion, "variant": variant, "records": len(pairs),
                "sourceIds": sorted({p["sourceId"] for _, p in pairs}),
                "loss": float(match[1]), "perplexity": float(match[2]),
                "logSha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
                "command": command,
            })
            print(f"{religion}/{variant}: loss{match[1]}, perplexity{match[2]}", flush=True)
            (experiment / "diagnostics.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
