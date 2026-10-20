#!/usr/bin/env python3
"""Convert a trained, merged Qwen3 model to MLC using an isolated CPU container.

Avoids the observed native macOS MLC wheel initialization failures. Downloads
official CPU packages inside a bounded container; does not publish artifacts.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "python@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f"
INNER = r'''
import json, pathlib, subprocess, sys
root = pathlib.Path("/experiment")
use_numpy = __USE_NUMPY__
def run(args):
    print("RUN", " ".join(args), flush=True)
    subprocess.run(args, check=True)
run([sys.executable, "-m", "pip", "install", "--no-cache-dir",
     "torch==2.14.1", "--index-url", "https://download.pytorch.org/whl/cpu"])
run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "--pre",
     "-f", "https://mlc.ai/wheels", "mlc-llm-nightly-cpu==0.26.dev6",
     "mlc-ai-nightly-cpu==0.26.dev246", "apache-tvm-ffi==0.1.15.post0",
     "psutil==7.2.2", "numpy==2.2.6"])
(root / "mlc-linux-requirements.txt").write_text(
    subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True))
if use_numpy:
    run([sys.executable, "/experiment/mlc-numpy-quant.py"])
else:
    run([sys.executable, "-m", "mlc_llm", "convert_weight",
         "/experiment/fused-bf16", "--quantization", "q4f16_1", "--device", "cpu",
         "-o", "/experiment/mlc-q4f16_1"])
run([sys.executable, "-m", "mlc_llm", "gen_config",
     "/experiment/fused-bf16", "--quantization", "q4f16_1",
     "--conv-template", "qwen3", "--context-window-size", "4096",
     "--prefill-chunk-size", "1024", "-o", "/experiment/mlc-q4f16_1"])
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / ".cache/training/qwen3-0.6b-v2")
    parser.add_argument("--numpy-quantizer", action="store_true",
                        help="Use the bounded NumPy q4f16_1 fallback after a TVM JIT failure.")
    args = parser.parse_args()
    experiment = args.experiment.resolve()
    if ROOT / ".cache/training" not in experiment.parents:
        raise ValueError("Expected an experiment under .cache/training.")
    if not (experiment / "fused-bf16/model.safetensors").exists():
        raise ValueError("Train and fuse the model first.")
    script = experiment / "mlc-convert-container.py"
    script.write_text(INNER.replace("__USE_NUMPY__", repr(args.numpy_quantizer)))
    if args.numpy_quantizer:
        shutil.copyfile(ROOT / "scripts/train_mlc_numpy_quant.py", experiment / "mlc-numpy-quant.py")
    container = "scripture-mlc-" + hashlib.sha256(str(experiment).encode()).hexdigest()[:10]
    command = ["docker", "run", "--name", container, "--platform", "linux/amd64",
               "--memory", "8g", "--cpus", "8",
               "--mount", f"type=bind,src={experiment},dst=/experiment",
               IMAGE, "python", "-u", "/experiment/mlc-convert-container.py"]
    exists = subprocess.run(["docker", "container", "inspect", container],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if exists:
        command = ["docker", "start", "--attach", container]
    manifest = {
        "status": "running", "startedAt": datetime.now(timezone.utc).isoformat(),
        "image": IMAGE, "platform": "linux/amd64", "command": command, "container": container,
        "reason": "Official native macOS MLC wheels failed in native library initialization.",
        "numpyQuantizerFallback": args.numpy_quantizer,
        "inputModel": str(experiment / "fused-bf16"),
        "inputWeightsSha256": hashlib.sha256((experiment / "fused-bf16/model.safetensors").read_bytes()).hexdigest(),
    }
    manifest_path = experiment / "mlc-export.json"
    def save():
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    save()
    start = time.monotonic()
    print(f"Converting; follow {experiment / 'mlc-export.log'}", flush=True)
    try:
        with (experiment / "mlc-export.log").open("w") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=900)
        if result.returncode:
            raise RuntimeError(f"MLC conversion failed ({result.returncode}); inspect mlc-export.log.")
        output = experiment / "mlc-q4f16_1"
        # TVM 0.26 renamed this file; the installed WebLLM 0.2.86 loader
        # still requests ndarray-cache.json. The shard schema is unchanged.
        if (output / "tensor-cache.json").exists():
            shutil.copyfile(output / "tensor-cache.json", output / "ndarray-cache.json")
        for name, source in (
            ("LICENSE", experiment / "fused-bf16/LICENSE"),
            ("CORPUS-NOTICES.txt", experiment / "corpus-notices.txt"),
            ("DATA-RIGHTS.json", experiment / "data-rights-and-splits.json"),
        ):
            shutil.copyfile(source, output / name)
        files = {p.name: {"bytes": p.stat().st_size,
                          "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(output.iterdir()) if p.is_file()}
        total = sum(item["bytes"] for item in files.values())
        if total >= 1_000_000_000:
            raise ValueError("MLC package exceeds the requested 1GB limit.")
        manifest.update(status="converted_browser_unverified", output=str(output),
                        bytes=total, files=files)
    except BaseException as error:
        if isinstance(error, (subprocess.TimeoutExpired, KeyboardInterrupt)):
            subprocess.run(["docker", "stop", "--time", "10", container],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30, check=False)
        manifest.update(status="failed", error=str(error))
        raise
    finally:
        manifest.update(seconds=round(time.monotonic() - start, 3),
                        finishedAt=datetime.now(timezone.utc).isoformat())
        save()
    print(f"MLC package: {output} ({total:,} bytes). Browser generation still requires verification.")


if __name__ == "__main__":
    main()
