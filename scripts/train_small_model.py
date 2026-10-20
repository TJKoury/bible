#!/usr/bin/env python3
"""Pinned, bounded Qwen3-0.6B QLoRA experiment on the comparative text corpus.

Use the isolated MLX environment. --stage all downloads the pinned <1GB base,
measures held-out loss, trains, evaluates and exports actual local weights.
It does not publish anything or certify theological answer quality.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request

from train_model import validate_dataset, require, sha256_file

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "mlx-community/Qwen3-0.6B-4bit"
REVISION = "73e3e38d981303bc594367cd910ea6eb48349da8"
UPSTREAM_ID = "Qwen/Qwen3-0.6B"
UPSTREAM_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
MODEL_SHA256 = "392e8d466d56100ada00eb82031fb854297fc9e389b7d303eba3af114e87bce2"
BASE = ROOT / ".cache/models/qwen3-0.6b-mlx-4bit"
DATA = ROOT / ".cache/training/research-v1"


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def download(url, target):
    if target.exists():
        return
    partial = target.with_name(target.name + ".partial")
    with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as stream:
        while block := response.read(1024 * 1024):
            stream.write(block)
    partial.replace(target)


def ensure_base(output):
    BASE.mkdir(parents=True, exist_ok=True)
    metadata_path = output / "base-provider-metadata.json"
    if not metadata_path.exists():
        with urllib.request.urlopen(
            f"https://huggingface.co/api/models/{MODEL_ID}/revision/{REVISION}?blobs=true",
            timeout=60,
        ) as response:
            metadata = json.load(response)
        write_json(metadata_path, metadata)
    metadata = json.loads(metadata_path.read_text())
    require(metadata["sha"] == REVISION, "Provider revision changed.")
    require(metadata["cardData"]["license"] == "apache-2.0", "Unexpected model license.")
    checked = {}
    for item in metadata["siblings"]:
        name = item["rfilename"]
        if name == ".gitattributes":
            continue
        require(Path(name).name == name, "Unexpected nested provider filename.")
        path = BASE / name
        download(f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}", path)
        raw = path.read_bytes()
        require(len(raw) == item["size"], f"Wrong provider file size: {name}")
        digest = hashlib.sha256(raw).hexdigest()
        if item.get("lfs"):
            require(digest == item["lfs"]["sha256"], f"Wrong provider SHA256: {name}")
        else:
            blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
            require(blob == item["blobId"], f"Wrong provider Git blob: {name}")
        checked[name] = {"sha256": digest, "bytes": len(raw)}
    require(checked["model.safetensors"]["sha256"] == MODEL_SHA256, "Base weight hash mismatch.")
    download(f"https://huggingface.co/{UPSTREAM_ID}/resolve/{UPSTREAM_REVISION}/LICENSE", BASE / "LICENSE")
    license_bytes = (BASE / "LICENSE").read_bytes()
    require(hashlib.sha1(f"blob {len(license_bytes)}\0".encode() + license_bytes).hexdigest()
            == "6634c8cc3133b3848ec74b9f275acaaa1ea618ab", "Upstream Apache license changed.")
    checked["LICENSE"] = {"sha256": sha256_file(BASE / "LICENSE"), "bytes": len(license_bytes)}
    total = sum(item["bytes"] for item in checked.values())
    require(total < 1_000_000_000, "Base model package exceeds the requested 1GB limit.")
    return {
        "id": MODEL_ID, "revision": REVISION, "path": str(BASE),
        "upstreamId": UPSTREAM_ID, "upstreamLicenseRevision": UPSTREAM_REVISION,
        "upstreamNote": "MLX model card names this upstream model but does not pin its conversion input revision. The revision above pins the license only.",
        "license": "Apache-2.0", "bytes": total, "files": checked,
    }


def artifacts(directory):
    return {str(p.relative_to(directory)): {"sha256": sha256_file(p), "bytes": p.stat().st_size}
            for p in sorted(directory.rglob("*")) if p.is_file() and ".cache" not in p.relative_to(directory).parts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("download", "baseline", "train", "evaluate", "export", "all"),
                        default="download")
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/training/qwen3-0.6b-v2")
    parser.add_argument("--iters", type=int, default=150)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-seq-length", type=int, default=1024)
    parser.add_argument("--learning-rate", type=float, default=2e-6)
    parser.add_argument("--layers", type=int, default=8)
    parser.add_argument("--rank", type=int, default=8)
    parser.add_argument("--lora-scale", type=float, default=16.0)
    args = parser.parse_args()
    require(platform.system() == "Darwin" and platform.machine() == "arm64", "Native Apple silicon required.")
    require(importlib.metadata.version("mlx-lm") == "0.32.2", "Use the pinned MLX-LM 0.32.2 environment.")
    require(1 <= args.iters <= 1000 and 1 <= args.batch_size <= 8
            and 256 <= args.max_seq_length <= 4096 and 0 < args.learning_rate <= 1e-3
            and 1 <= args.layers <= 28 and 1 <= args.rank <= 64 and 0 < args.lora_scale <= 64,
            "Parameters exceed this bounded experiment's limits.")
    output = args.output.resolve()
    require(ROOT / ".cache/training" in output.parents and output != DATA,
            "Use a separate experiment directory under .cache/training/.")
    output.mkdir(parents=True, exist_ok=True)
    run_path = output / "run.json"
    run = json.loads(run_path.read_text()) if run_path.exists() else {
        "createdAt": now(), "status": "setting_up", "stages": {},
        "task": "Continued-text QLoRA adaptation; not supervised theological answer training",
        "customWeights": False, "browserReady": False, "approvedForAnswers": False,
    }
    if args.stage == "download" or not run.get("base"):
        run["base"] = ensure_base(output)
    require(sha256_file(BASE / "model.safetensors") == MODEL_SHA256, "Base weights were modified.")
    validation = validate_dataset(DATA)
    if run.get("dataset"):
        require(run["dataset"] == validation, "Dataset changed; create a new experiment.")
    run["dataset"] = validation
    parameters = {
        "iterations": args.iters, "batchSize": args.batch_size,
        "maxSequenceLength": args.max_seq_length, "learningRate": args.learning_rate,
        "loraRank": args.rank, "loraScale": args.lora_scale, "layers": args.layers, "seed": 17,
        "quantizationBits": 4, "quantizationGroupSize": 64,
    }
    if run.get("parameters"):
        require(run["parameters"] == parameters, "Parameters changed; create a new experiment.")
    run["parameters"] = parameters
    run["platform"] = {"system": platform.system(), "machine": platform.machine(),
                       "python": platform.python_version()}
    run["packages"] = {name: importlib.metadata.version(name) for name in
                       ("mlx-lm", "mlx", "mlx-metal", "transformers", "tokenizers")}
    (output / "requirements-lock.txt").write_text(
        subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True))
    shutil.copyfile(DATA / "rights-and-splits.json", output / "data-rights-and-splits.json")
    shutil.copyfile(ROOT / "public/licenses/research-notices.txt", output / "corpus-notices.txt")
    write_json(run_path, run)

    def execute(stage, command, timeout=1800):
        existing = run["stages"].get(stage)
        if existing and existing.get("status") == "completed":
            print(f"Already completed: {stage}", flush=True)
            return
        info = {"status": "running", "startedAt": now(), "command": command}
        run["stages"][stage] = info
        run["status"] = stage
        write_json(run_path, run)
        print(f"Starting {stage}; log {output / (stage + '.log')}", flush=True)
        started = time.monotonic()
        try:
            with (output / f"{stage}.log").open("w") as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=timeout, check=False)
            require(result.returncode == 0, f"{stage} failed; see its log.")
            info["status"] = "completed"
            info["exitCode"] = result.returncode
        except BaseException as error:
            info["status"] = "failed"
            info["error"] = str(error)
            run["status"] = "failed"
            raise
        finally:
            info["seconds"] = round(time.monotonic() - started, 3)
            info["finishedAt"] = now()
            info["logSha256"] = sha256_file(output / f"{stage}.log")
            write_json(run_path, run)
        print(f"Completed {stage} in {info['seconds']:.1f}s", flush=True)

    common = [sys.executable, "-m", "mlx_lm", "lora", "--model", str(BASE),
              "--data", str(DATA), "--batch-size", str(args.batch_size),
              "--max-seq-length", str(args.max_seq_length), "--seed", "17"]
    adapter = output / "adapters"
    if args.stage in ("baseline", "all"):
        execute("baseline-loss", common + ["--test", "--test-batches", "-1", "--batch-size", "1", "--adapter-path", ""])
    if args.stage in ("train", "all"):
        require(run["stages"].get("baseline-loss", {}).get("status") == "completed",
                "Run baseline stage before training.")
        config = {"lora_parameters": {"rank": args.rank, "dropout": 0.0, "scale": args.lora_scale}}
        # JSON is a YAML subset accepted by MLX's config loader.
        write_json(output / "lora-config.yaml", config)
        execute("training", common + [
            "--train", "--fine-tune-type", "lora", "--num-layers", str(args.layers),
            "--adapter-path", str(adapter), "--iters", str(args.iters),
            "--learning-rate", str(args.learning_rate), "--steps-per-report", "10",
            "--steps-per-eval", "50", "--val-batches", "-1", "--save-every", "50",
            "--config", str(output / "lora-config.yaml"),
        ])
        run["customWeights"] = True
        run["adapterArtifacts"] = artifacts(adapter)
        write_json(run_path, run)
    if args.stage in ("evaluate", "all"):
        require((adapter / "adapters.safetensors").exists(), "No trained adapter found.")
        execute("adapted-loss", common + ["--test", "--test-batches", "-1", "--batch-size", "1",
                                         "--adapter-path", str(adapter)])
        execute("answer-probes", [sys.executable, str(ROOT / "scripts/train_small_evaluate.py"),
                                 "--base", str(BASE), "--adapter", str(adapter),
                                 "--output", str(output / "answer-probes.json")])
    if args.stage in ("export", "all"):
        require((adapter / "adapters.safetensors").exists(), "No trained adapter found.")
        # Dequantize before MLC conversion. A second, MLX-specific 4-bit package
        # remains useful locally and must not be mistaken for MLC tensors.
        fused = output / "fused-bf16"
        quantized = output / "fused-mlx-4bit"
        execute("fuse-bf16", [sys.executable, "-m", "mlx_lm", "fuse", "--model", str(BASE),
                             "--adapter-path", str(adapter), "--dequantize", "--save-path", str(fused)])
        execute("requantize-mlx", [sys.executable, "-m", "mlx_lm", "convert",
                                  "--hf-path", str(fused), "--mlx-path", str(quantized),
                                  "-q", "--q-bits", "4", "--q-group-size", "64"])
        for directory in (fused, quantized):
            shutil.copyfile(BASE / "LICENSE", directory / "LICENSE")
            shutil.copyfile(output / "corpus-notices.txt", directory / "CORPUS-NOTICES.txt")
            shutil.copyfile(output / "data-rights-and-splits.json", directory / "DATA-RIGHTS.json")
        run["exports"] = {
            "fusedBf16": {"path": str(fused), "files": artifacts(fused)},
            "mlx4bit": {"path": str(quantized), "files": artifacts(quantized)},
        }
        quantized_bytes = sum(p.stat().st_size for p in quantized.rglob("*") if p.is_file())
        require(quantized_bytes < 1_000_000_000, "Final quantized MLX package exceeds 1GB.")
        run["exports"]["mlx4bit"]["bytes"] = quantized_bytes
    for stage, key in (("baseline-loss", "baselineHeldout"), ("adapted-loss", "adaptedHeldout")):
        if run["stages"].get(stage, {}).get("status") == "completed":
            log = (output / f"{stage}.log").read_text()
            result = re.search(r"Test loss ([0-9]+\.[0-9]+), Test ppl ([0-9]+\.[0-9]+)", log)
            if result:
                run[key] = {"loss": float(result[1]), "perplexity": float(result[2]),
                            "scope": "all held-out test documents, token truncation at configured length"}
    run["status"] = "experiment_completed" if args.stage == "all" else f"{args.stage}_completed"
    run["updatedAt"] = now()
    run.setdefault("qualityStatus", "Unapproved experimental weights. Held-out loss and answer probes are not a theological benchmark.")
    write_json(run_path, run)
    print(f"Manifest: {run_path}", flush=True)


if __name__ == "__main__":
    main()
