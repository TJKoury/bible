#!/usr/bin/env python3
"""Validate and plan an MLX-LM LoRA experiment; train only with --train.

This wrapper uses historical text for continued-pretraining-style adaptation,
not reviewed question/answer labels. It never downloads models or installs tools.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MLX_VERSION = "0.32.2"
MODEL_ID = "Qwen/Qwen3-4B"
REVISION = "1cfa9a7208912126459214e8b04321603b3df60c"
# Provider API metadata for the pinned revision; LFS objects use SHA256.
MODEL_SHA256 = {
    "model-00001-of-00003.safetensors": "328a91d3122359d5547f9d79521205bc0a46e1f79a792dfe650e99fc2d651223",
    "model-00002-of-00003.safetensors": "6cd087b316306a68c562436b5492edbcf6e16c6dba3a1308279caa5a58e21ca5",
    "model-00003-of-00003.safetensors": "e4bf436957184f4eeb86a80e9db394503f1f56446b2e6b7edeac5b81470f4ca1",
    "tokenizer.json": "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4",
}
MODEL_GIT_BLOBS = {
    "LICENSE": "6634c8cc3133b3848ec74b9f275acaaa1ea618ab",
    "config.json": "e49eccdc32f36da9c09cfa0e737084f9e0105e5e",
    "generation_config.json": "20a8a9156fc8c3f25295ca067f61fdf120d517c5",
    "model.safetensors.index.json": "95c0a0059df040d75dc6c396b174382cf61d2f91",
    "tokenizer_config.json": "417d038a63fa3de29cfde265caedae14d1a58d92",
}


def sha256_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_dataset(data):
    """Tie every training record to the locked, rights-reviewed source corpus."""
    rights_path = data / "rights-and-splits.json"
    rights = read_json(rights_path)
    catalog_path = ROOT / "public/data/research/manifest.json"
    chunks_path = ROOT / "public/data/research/chunks.json"
    catalog = read_json(catalog_path)
    source_catalog = {s["id"]: s for s in catalog["sources"]}
    chunks = {c["id"]: c for c in read_json(chunks_path)}
    require(rights.get("sourceManifestSha256") == sha256_file(catalog_path), "Source manifest changed; regenerate the training export.")
    require(rights.get("chunksSha256") == sha256_file(chunks_path), "Research passages changed; regenerate the training export.")
    sources = {s["id"]: s for s in rights["sources"]}
    require(set(sources) == set(source_catalog), "Rights manifest does not match the source catalog.")
    for sid, source in sources.items():
        original = source_catalog[sid]
        require(source.get("trainingEligible") is True and original.get("trainingEligible") is True,
                f"Source is not eligible for this export: {sid}")
        for field in ("sha256", "license", "licenseUrl", "sourceUrl", "tradition"):
            require(source.get(field) and source[field] == original[field], f"Source rights/provenance mismatch: {sid}/{field}")
    seen_ids, split_sources, summary = set(), {}, {}
    for split in ("train", "valid", "test"):
        path = data / f"{split}.jsonl"
        require(sha256_file(path) == rights["splits"][split]["sha256"], f"{split} file hash mismatch.")
        records = read_jsonl(path)
        provenance = read_jsonl(data / f"{split}.provenance.jsonl")
        require(len(records) == len(provenance) > 0, f"{split} must have matching nonempty text and provenance.")
        used, religions, words = set(), Counter(), 0
        for row, proof in zip(records, provenance):
            require(set(row) == {"text"} and isinstance(row["text"], str) and row["text"].strip(),
                    "This wrapper accepts only text records; reviewed SFT is a separate dataset.")
            sid, record_id = proof["sourceId"], proof["id"]
            require(record_id not in seen_ids, f"Repeated passage across splits: {record_id}")
            seen_ids.add(record_id)
            require(sid in sources and sources[sid].get("split") == split, f"Source split mismatch: {sid}")
            original = chunks.get(record_id)
            require(original and original["sourceId"] == sid and original["text"] == row["text"],
                    f"Record does not match the research corpus: {record_id}")
            require(proof.get("locator") == original["locator"], f"Locator changed: {record_id}")
            require(proof.get("sourceSha256") == sources[sid]["sha256"], f"Source hash changed: {record_id}")
            require(proof.get("textSha256") == hashlib.sha256(row["text"].encode()).hexdigest(),
                    f"Text hash changed: {record_id}")
            used.add(sid)
            religions[sources[sid]["tradition"]] += 1
            words += len(row["text"].split())
        expected = rights["splits"][split]
        require(used == set(expected["sources"]), f"{split} source list mismatch.")
        require(len(records) == expected["passages"] and words == expected["words"], f"{split} totals mismatch.")
        require(dict(religions) == expected["religionCounts"], f"{split} tradition counts mismatch.")
        require(set(religions) == {"Christianity", "Judaism", "Islam"}, f"{split} lacks a comparison tradition.")
        split_sources[split] = used
        summary[split] = dict(passages=len(records), words=words, sources=sorted(used),
                              religionCounts=dict(religions), sha256=sha256_file(path))
    require(not (split_sources["train"] & split_sources["valid"]
                 or split_sources["train"] & split_sources["test"]
                 or split_sources["valid"] & split_sources["test"]), "Document leakage between splits.")
    return dict(rightsManifestSha256=sha256_file(rights_path),
                sourceManifestSha256=sha256_file(catalog_path),
                corpusSha256=sha256_file(chunks_path), splits=summary)


def validate_model(model):
    """No remote download: verify local bytes against the declared HF revision."""
    checked = {}
    for name, expected in MODEL_SHA256.items():
        path = model / name
        require(path.is_file(), f"Missing model file {path}. Download the pinned base model first.")
        actual = sha256_file(path)
        require(actual == expected, f"Pinned model checksum mismatch: {name}")
        checked[name] = {"sha256": actual, "bytes": path.stat().st_size}
    for name, expected in MODEL_GIT_BLOBS.items():
        path = model / name
        require(path.is_file(), f"Missing model metadata: {path}")
        data = path.read_bytes()
        actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        require(actual == expected, f"Pinned model metadata mismatch: {name}")
        checked[name] = {"gitBlobSha1": actual, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    require(read_json(model / "config.json").get("model_type") == "qwen3", "Expected the pinned dense Qwen3 model.")
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true", help="Validate data and save a plan; this is the default.")
    action.add_argument("--train", action="store_true", help="Run the MLX experiment with already-installed tools and local weights.")
    parser.add_argument("--data", type=Path, default=ROOT / ".cache/training/research-v1")
    parser.add_argument("--model", type=Path, default=ROOT / ".cache/models/qwen3-4b")
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/training/qwen3-4b-experiment")
    parser.add_argument("--iters", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--num-layers", type=int, default=16)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    require(args.iters > 0 and args.batch_size > 0 and 1 <= args.num_layers <= 36
            and args.max_seq_length > 0 and args.learning_rate > 0, "Invalid training parameter.")
    data, model, output = args.data.resolve(), args.model.resolve(), args.output.resolve()
    require(ROOT / ".cache" in output.parents, "Write training artifacts under this project's .cache directory.")
    validation = validate_dataset(data)
    adapters = output / "adapters"
    command = [sys.executable, "-m", "mlx_lm", "lora", "--model", str(model), "--train",
               "--data", str(data), "--fine-tune-type", "lora",
               "--adapter-path", str(adapters), "--iters", str(args.iters),
               "--batch-size", str(args.batch_size), "--num-layers", str(args.num_layers),
               "--max-seq-length", str(args.max_seq_length), "--learning-rate", str(args.learning_rate),
               "--seed", str(args.seed), "--steps-per-report", "10",
               "--steps-per-eval", "50", "--val-batches", "10", "--save-every", "50",
               "--grad-checkpoint"]
    plan = dict(status="planned_only", task="LoRA domain adaptation using plain text; not supervised answer training",
                createdAt=datetime.now(timezone.utc).isoformat(), command=command,
                model=dict(id=MODEL_ID, revision=REVISION, path=str(model), license="Apache-2.0",
                           verifiedLocalFiles=False),
                requiredMlxLmVersion=MLX_VERSION, platform=platform.platform(), python=sys.version,
                dataset=validation, parameters=vars(args).copy(),
                evaluationStatus="Not evaluated; no theological accuracy or browser compatibility claim.")
    plan["parameters"] = {key: str(value) if isinstance(value, Path) else value
                          for key, value in plan["parameters"].items()}
    output.mkdir(parents=True, exist_ok=True)
    (output / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    print(shlex.join(command))
    print(f"Plan: {output / 'plan.json'}")
    if not args.train:
        print("Dry run: data validated. No dependencies installed, model downloaded, or training started.")
        return
    require(platform.system() == "Darwin" and platform.machine() == "arm64", "This recipe targets native Apple silicon macOS.")
    require(importlib.metadata.version("mlx-lm") == MLX_VERSION, f"Use the verified mlx-lm[train]=={MLX_VERSION} environment.")
    require(not (output / "run.json").exists() and not adapters.exists(), "Choose a fresh --output; existing runs are not overwritten.")
    plan["model"]["files"] = validate_model(model)
    plan["model"]["verifiedLocalFiles"] = True
    plan["status"] = "running"
    run_path = output / "run.json"

    def save_run():
        run_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")

    save_run()
    try:
        with (output / "training.log").open("w") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
        plan["exitCode"] = result.returncode
        plan["status"] = "training_completed_unvalidated" if result.returncode == 0 else "failed"
        if result.returncode == 0:
            weights = adapters / "adapters.safetensors"
            require(weights.is_file(), "MLX exited successfully but no adapter weights were found.")
            plan["adapterSha256"] = sha256_file(weights)
    except BaseException as error:
        plan["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        plan["error"] = str(error)
        raise
    finally:
        plan["finishedAt"] = datetime.now(timezone.utc).isoformat()
        save_run()
    print(f"{plan['status']}; inspect {output / 'training.log'}. Evaluation and WebGPU conversion remain separate.")
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, KeyError, importlib.metadata.PackageNotFoundError) as error:
        raise SystemExit(f"Training setup error: {error}") from error
