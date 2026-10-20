#!/usr/bin/env python3
"""CPU fallback for the q4f16_1 quantizer when TVM's JIT crashes.

Uses the official MLC model mapping, loader and tensor-cache writer. Only the
group quantization calculation is replaced, following GroupQuantize._quantize:
group32 max-abs/7 scales, rounded/clipped unsigned nibbles, 8 values per uint32.
This is limited to the dense Qwen3 matrix layout used by this experiment.
"""
import json
from pathlib import Path
import runpy
import sys

import numpy as np


def quantize_array(array, group_size=32):
    values = np.asarray(array, dtype=np.float16)
    if values.ndim != 2 or values.shape[1] % group_size or group_size != 32:
        raise ValueError("Fallback supports 2D matrices with width divisible by32 only.")
    rows, columns = values.shape
    packed = np.empty((rows, columns // 8), dtype=np.uint32)
    scales = np.empty((rows, columns // group_size), dtype=np.float16)
    shifts = np.arange(8, dtype=np.uint32) * np.uint32(4)
    for start in range(0, rows, 512):
        stop = min(start + 512, rows)
        groups = values[start:stop].reshape(stop - start, columns // group_size, group_size)
        scale = (np.max(np.abs(groups), axis=-1) / np.float16(7)).astype(np.float16)
        normalized = np.divide(groups, scale[..., None], out=np.zeros_like(groups),
                               where=scale[..., None] != 0)
        offset = (normalized + np.float16(7)).astype(np.float16)
        # TVM's round intrinsic uses nearest integer, ties away from zero.
        # The shifted values are nonnegative; floor(x+0.5) is equivalent.
        rounded = np.floor(offset.astype(np.float32) + np.float32(0.5))
        integers = np.clip(rounded, 0, 14).astype(np.uint32)
        words = integers.reshape(stop - start, columns // 8, 8)
        packed[start:stop] = np.bitwise_or.reduce(words << shifts, axis=-1)
        scales[start:stop] = scale
    return packed, scales


def validate_fixture():
    sample = np.array([list(range(-7, 8)) + [0] * 17], dtype=np.float16)
    packed, scales = quantize_array(sample)
    unpacked = np.stack([(packed >> np.uint32(4 * i)) & np.uint32(15)
                         for i in range(8)], axis=-1).reshape(1, 32)
    reconstructed = (unpacked.astype(np.float16) - 7) * np.repeat(scales, 32, axis=-1)
    if not np.array_equal(reconstructed, sample):
        raise ValueError("Quantization packing fixture failed")
    zeros, zero_scales = quantize_array(np.zeros((2, 64), dtype=np.float16))
    if not np.all(zero_scales == 0) or not np.all(zeros == np.uint32(0x77777777)):
        raise ValueError("Zero-group fixture failed")


def main():
    validate_fixture()
    import tvm
    from mlc_llm.quantization.group_quantization import GroupQuantize
    counter = {"method": "numpy CPU implementation of MLC q4f16_1 group quantization",
               "matrices": 0, "parameters": 0, "fixturePassed": True,
               "limitation": "Browser generation and numerical end-to-end equivalence are separate checks."}

    def quantize_weight(self, weight, axis=-1, output_transpose=False):
        if (self.name != "q4f16_1" or self.group_size != 32
                or self.storage_dtype != "uint32" or self.model_dtype != "float16"
                or self.linear_weight_layout != "NK" or axis not in (-1, 1)):
            raise ValueError("Unsupported fallback quantizer configuration.")
        data = weight.numpy()
        packed, scales = quantize_array(data)
        if output_transpose:
            packed, scales = packed.T, scales.T
        counter["matrices"] += 1
        counter["parameters"] += int(data.size)
        Path("/experiment/mlc-numpy-quantization.json").write_text(json.dumps(counter, indent=2) + "\n")
        return [tvm.runtime.tensor(np.ascontiguousarray(packed), device=weight.device),
                tvm.runtime.tensor(np.ascontiguousarray(scales), device=weight.device)]

    GroupQuantize.quantize_weight = quantize_weight
    sys.argv = ["mlc_llm", "convert_weight", "/experiment/fused-bf16",
                "--quantization", "q4f16_1", "--device", "cpu",
                "-o", "/experiment/mlc-q4f16_1"]
    runpy.run_module("mlc_llm", run_name="__main__")


if __name__ == "__main__":
    main()
