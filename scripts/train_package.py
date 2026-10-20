#!/usr/bin/env python3
"""Package experimental trained weights with public, path-free audit metadata."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def metric(path):
    if not path.exists():
        return None
    match = re.search(r"Test loss ([0-9]+\.[0-9]+), Test ppl ([0-9]+\.[0-9]+)", path.read_text())
    return {"loss": float(match[1]), "perplexity": float(match[2])} if match else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / ".cache/training/qwen3-0.6b-v2")
    parser.add_argument("--format", choices=("mlx", "mlc"), default="mlx")
    parser.add_argument("--skip-public-report", action="store_true",
                        help="Package without rewriting the app-imported public report during browser testing.")
    args = parser.parse_args()
    experiment = args.experiment.resolve()
    run = json.loads((experiment / "run.json").read_text())
    folder = experiment / ("fused-mlx-4bit" if args.format == "mlx" else "mlc-q4f16_1")
    required = "model.safetensors" if args.format == "mlx" else "ndarray-cache.json"
    if not (folder / required).exists():
        raise ValueError(f"Missing actual model output: {required}")
    report = {
        "id": "scripture-qwen3-0.6b-v2",
        "status": "experimental", "customWeights": True,
        "format": "MLX affine 4-bit" if args.format == "mlx" else "MLC q4f16_1",
        "browserVerified": False, "approvedForTheologicalAnswers": False,
        "base": {k: run["base"][k] for k in ("id", "revision", "license", "bytes")},
        "baseWeightsSha256": run["base"]["files"]["model.safetensors"]["sha256"],
        "training": {**run["parameters"], "trainableParameters": 1441792,
                     "seconds": run["stages"]["training"]["seconds"],
                     "objective": "Continued-text QLoRA adaptation, not supervised theological Q&A"},
        "data": {
            "sources": 13, "religions": ["Christianity", "Judaism", "Islam"],
            "trainPassages": 1551, "validationPassages": 198, "testPassages": 177,
            "equalPassagesPerReligion": True, "splitUnit": "source edition",
            "licenseScope": "Historical public-domain-in-the-USA texts; source rights and credits retained.",
            "encyclopediaIncluded": False,
            "sourceManifestSha256": run["dataset"]["sourceManifestSha256"],
            "corpusSha256": run["dataset"]["corpusSha256"],
        },
        "heldoutMetrics": {
            "base": metric(experiment / "baseline-loss.log"),
            "adapter": metric(experiment / "adapted-loss.log"),
            "mergedBf16": metric(experiment / "fused-bf16-loss.log"),
            "requantizedMlx4bit": metric(experiment / "quantized-loss.log"),
            "mlcBrowser": None,
        },
        "probeReview": [
            "Conservative adapter preserves named Romans 9 disagreement and distinguishes a survey from endorsement.",
            "It declines an unsupported excavation quotation.",
            "It still makes passage-summary errors, omits requested source IDs, and overstates limits to interfaith comparison.",
            "Seven ad hoc qualitative probes are not an expert-reviewed theological benchmark.",
        ],
        "limitations": [
            "Do not present adapter-only loss improvement as a browser-model result; requantization loses most of the observed gain.",
            "Test/probe results were inspected during development; a new withheld acceptance benchmark is needed.",
            "Historical English source coverage is incomplete and unequal within each religion.",
            "Long text is truncated at 1024 tokens; final test includes all177 records at batch size1.",
            "A pretrained model can contain prior exposure to these public-domain sources.",
            "Custom training does not establish citation reliability, religious neutrality or theological expertise.",
        ],
        "firstExperiment": {
            "status": "rejected", "iterations": 200,
            "loss": 4.585, "perplexity": 97.989,
            "reason": "Held-out degradation and repetitive, ungrounded answers.",
        },
        "licenses": {
            "baseAndModel": "Apache-2.0; original license and modifications notice retained.",
            "corpus": "See DATA-RIGHTS.json and CORPUS-NOTICES.txt.",
        },
    }
    diagnostics = experiment / "diagnostics.json"
    if diagnostics.exists():
        report["heldoutSourceMetrics"] = [
            {k: row[k] for k in ("religion", "variant", "records", "sourceIds", "loss", "perplexity")}
            for row in json.loads(diagnostics.read_text())["results"]
        ]
    card = (
        "# Scripture Qwen3 0.6B v2 — experimental\n\n"
        "Modified from mlx-community/Qwen3-0.6B-4bit by a150-step QLoRA training run "
        "on historical Christian, Jewish and Muslim texts. No preferred tradition "
        "was designated. This is an experimental research artifact, not a validated "
        "theological authority. Use retrieval sources and verify claims.\n\n"
        "The original Qwen base is licensed under Apache-2.0; see LICENSE. "
        "Model weights were modified by LoRA adaptation, fusion and quantization. "
        "Historical corpus credits, source rights and source-separated splits are "
        "retained in DATA-RIGHTS.json and CORPUS-NOTICES.txt. No Wikipedia text was "
        "used in this training run.\n\n"
        "TRAINING-RESULT.json reports actual pre/post-quantization results and "
        "limitations. ANSWER-PROBES.json includes actual outputs, including errors. "
        "Adapter-only improvements must not be described as browser-model gains. "
        "MLX artifacts require MLX; MLC artifacts require a compatible WebLLM "
        "library and separate browser verification. Download size is below1GB; "
        "runtime memory can be larger.\n"
    )
    (folder / "MODEL-CARD.md").write_text(card)
    (folder / "TRAINING-RESULT.json").write_text(json.dumps(report, indent=2) + "\n")
    shutil.copyfile(experiment / "answer-probes.json", folder / "ANSWER-PROBES.json")
    if (experiment / "quantized-answer-probes.json").exists():
        shutil.copyfile(experiment / "quantized-answer-probes.json", folder / "MLX-QUANTIZED-PROBES.json")
    # These source files contain no private paths. Fail if later tool versions
    # introduce such fields into tokenizer metadata or report artifacts.
    for path in folder.iterdir():
        if path.suffix in (".json", ".md", ".txt"):
            text = path.read_text()
            if "/Users/" in text or "/private/" in text or "/experiment/" in text:
                raise ValueError(f"Private/local path found in public package: {path.name}")
    files = {p.name: {"bytes": p.stat().st_size, "sha256": digest(p)}
             for p in sorted(folder.iterdir()) if p.is_file() and p.name != "FILES.json"}
    total = sum(row["bytes"] for row in files.values())
    if total >= 1_000_000_000:
        raise ValueError("Package exceeds1GB.")
    (folder / "FILES.json").write_text(json.dumps({"files": files, "bytes": total}, indent=2) + "\n")
    release = experiment / "release"
    release.mkdir(exist_ok=True)
    name = "scripture-qwen3-0.6b-v2-" + ("mlx4bit" if args.format == "mlx" else "mlc-q4f16_1")
    archive_root = name if args.format == "mlx" else "scripture-qwen3-0.6b-v2"
    archive = release / f"{name}.tar.gz"
    with archive.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped, \
            tarfile.open(fileobj=zipped, mode="w") as tar:
        for path in sorted(folder.iterdir()):
            if not path.is_file():
                continue
            info = tar.gettarinfo(str(path), arcname=f"{archive_root}/{path.name}")
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as stream:
                tar.addfile(info, stream)
    summary = {
        **report, "packageFilesBytes": sum(p.stat().st_size for p in folder.iterdir() if p.is_file()),
        "archive": {"name": archive.name, "root": archive_root,
                    "bytes": archive.stat().st_size, "sha256": digest(archive)},
    }
    (release / f"{name}.json").write_text(json.dumps(summary, indent=2) + "\n")
    if not args.skip_public_report:
        (ROOT / "docs/training-result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"archive": str(archive), **summary["archive"],
                      "packageDirectory": str(folder), "bytes": summary["packageFilesBytes"]}, indent=2))


if __name__ == "__main__":
    main()
