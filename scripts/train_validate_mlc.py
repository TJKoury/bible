#!/usr/bin/env python3
"""Validate exported MLC shard layout and sampled reconstruction error."""
import argparse
import hashlib
import json
from pathlib import Path

import mlx.core as mx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / ".cache/training/qwen3-0.6b-v2")
    args = parser.parse_args()
    experiment = args.experiment.resolve()
    folder = experiment / "mlc-q4f16_1"
    cache = json.loads((folder / "ndarray-cache.json").read_text())
    reference = json.loads((ROOT / ".cache/training/toolchain/mlc-reference-ndarray-cache.json").read_text())
    weights = mx.load(str(experiment / "fused-bf16/model.safetensors"))
    records = {}
    for shard in cache["records"]:
        path = folder / shard["dataPath"]
        if path.stat().st_size != shard["nbytes"]:
            raise ValueError(f"Shard length mismatch: {path.name}")
        if hashlib.md5(path.read_bytes()).hexdigest() != shard["md5sum"]:
            raise ValueError(f"Shard MD5 mismatch: {path.name}")
        for record in shard["records"]:
            if record["byteOffset"] + record["nbytes"] > shard["nbytes"]:
                raise ValueError("Record outside shard")
            records[record["name"]] = {
                **record, "array": np.memmap(path, mode="r", offset=record["byteOffset"],
                                             dtype=record["dtype"], shape=tuple(record["shape"]))}
    expected = [p for shard in reference["records"] for p in shard["records"]]
    if len(expected) != len(records):
        raise ValueError("Parameter count differs from official model")
    for p in expected:
        actual = records[p["name"]]
        if any(actual[k] != p[k] for k in ("shape", "dtype", "format", "nbytes")):
            raise ValueError(f"Parameter schema differs: {p['name']}")
    checked, samples, max_error = 0, 0, 0.0
    for name, item in records.items():
        if not name.endswith(".q_weight"):
            continue
        stem = name.removesuffix(".q_weight")
        if stem.endswith(".self_attn.c_attn"):
            prefix = stem.removesuffix("c_attn")
            source = mx.concatenate([weights[prefix + part + ".weight"]
                                     for part in ("q_proj", "k_proj", "v_proj")], axis=0)
        elif stem.endswith(".mlp.gate_up_proj"):
            prefix = stem.removesuffix("gate_up_proj")
            source = mx.concatenate([weights[prefix + part + ".weight"]
                                     for part in ("gate_proj", "up_proj")], axis=0)
        else:
            source = weights[stem + ".weight"]
        row_ids = np.unique(np.linspace(0, source.shape[0] - 1, min(96, source.shape[0]), dtype=int))
        original = np.array(source[mx.array(row_ids)].astype(mx.float32)).astype(np.float16).astype(np.float32)
        packed = np.asarray(item["array"][row_ids], dtype=np.uint32)
        scales = np.asarray(records[stem + ".q_scale"]["array"][row_ids], dtype=np.float32)
        nibbles = np.stack([(packed >> np.uint32(i * 4)) & np.uint32(15)
                            for i in range(8)], axis=-1).reshape(original.shape)
        if not np.isfinite(scales).all() or not (scales >= 0).all() or np.any(nibbles > 14):
            raise ValueError("Invalid scales or packed values")
        expanded = np.repeat(scales, 32, axis=1)
        decoded = (nibbles.astype(np.float32) - 7) * expanded
        error = np.abs(decoded - original)
        # Half-step rounding bound, allowing FP16 arithmetic error near ties.
        if not np.all(error <= expanded * 0.52 + 0.00001):
            raise ValueError(f"Quantization reconstruction error exceeded bound: {stem}")
        max_error = max(max_error, float(error.max()))
        checked += 1
        samples += int(original.size)
    report = {
        "parameterSchemaMatchesOfficialModel": True, "parameters": len(records),
        "shardsVerified": len(cache["records"]), "quantizedMatricesSampled": checked,
        "sampledWeightValues": samples, "finiteScalesAndValidNibbles": True,
        "reconstructionBoundPassed": "abs(decoded-original) <=0.52*groupScale +0.00001",
        "maximumObservedAbsoluteError": max_error,
        "referenceModel": "mlc-ai/Qwen3-0.6B-q4f16_1-MLC",
        "referenceCacheSha256": hashlib.sha256(
            (ROOT / ".cache/training/toolchain/mlc-reference-ndarray-cache.json").read_bytes()).hexdigest(),
        "browserGenerationVerified": False,
        "limitation": "Structural and sampled numerical validation; not browser output or theological quality validation.",
    }
    (folder / "CONVERSION-VALIDATION.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
