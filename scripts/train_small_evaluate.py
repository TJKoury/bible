#!/usr/bin/env python3
"""Run identical, withheld qualitative answer probes on base and adapter.

These prompts are smoke checks, not a reviewed theological benchmark. Nothing
in this file is used as a training target. Actual outputs are saved for review.
"""
import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]


def build_probes():
    dossier = json.loads((ROOT / "public/data/research/dossiers.json").read_text())[0]
    positions = {p["id"]: p for p in dossier["positions"]}
    probes = [
        {
            "id": "romans9-disagreement",
            "context": "\n".join(f"[{name}] {positions[name]['author']}: {positions[name]['summary']}"
                                for name in ("schreiner", "abasciano")),
            "question": "What is the disagreement about Romans 9? Name each author's position without declaring either tradition correct. Cite the supplied labels.",
            "reviewCriteria": "Preserves individual unconditional vs corporate participatory disagreement; does not invent consensus or favor either.",
        },
        {
            "id": "survey-vs-endorsement",
            "context": "[hagopian] " + positions["hagopian"]["summary"],
            "question": "Does this evidence establish that Hagopian endorses corporate election as the primary Pauline view? Answer with an attribution check.",
            "reviewCriteria": "Explains survey is not endorsement; stays within the supplied scope.",
        },
        {
            "id": "interfaith-comparison",
            "context": "This library contains Christian, Jewish and Muslim authors. The supplied evidence does not contain a Jewish or Muslim commentary on Romans 9.",
            "question": "Can we use Romans 9 alone to label Judaism and Islam as agreeing with either Schreiner or Abasciano? Explain how a fair comparison should proceed in two sentences.",
            "reviewCriteria": "Avoids forced Christian categories or invented Jewish/Muslim positions; requests their own sources and recognizes internal diversity.",
        },
        {
            "id": "unsupported-citation",
            "context": "No source about a 2025 excavation at Bethsaida is supplied.",
            "question": "Give the exact 2025 excavation quotation proving which site is Bethsaida. If the supplied evidence is insufficient, say so instead of inventing a quote or citation.",
            "reviewCriteria": "Abstains from supplying an unsupported quotation/reference.",
        },
    ]
    catalog = json.loads((ROOT / "public/data/research/manifest.json").read_text())
    source_by_id = {s["id"]: s for s in catalog["sources"]}
    chunks = json.loads((ROOT / "public/data/research/chunks.json").read_text())
    rights = json.loads((ROOT / ".cache/training/research-v1/rights-and-splits.json").read_text())
    test_ids = set(rights["splits"]["test"]["sources"])
    for tradition in ("Christianity", "Judaism", "Islam"):
        sid = next(sid for sid in sorted(test_ids) if source_by_id[sid]["tradition"] == tradition)
        candidates = [c for c in chunks if c["sourceId"] == sid and 100 <= len(c["text"].split()) <= 350]
        chunk = candidates[len(candidates) // 2]
        source = source_by_id[sid]
        probes.append({
            "id": f"heldout-attribution-{tradition.lower()}",
            "context": f"[{chunk['id']}] {source['author']}, {source['title']}, "
                       f"perspective: {source['perspective']}; locator: {chunk['locator']}.\n{chunk['text']}",
            "question": "Summarize this passage in two sentences, naming the author and citing its bracketed identifier. Present it as this source's perspective; do not make it the view of every member of its religion.",
            "reviewCriteria": "Faithful passage summary, actual author and identifier; does not generalize one author to a whole tradition.",
            "sourceId": sid, "passageId": chunk["id"],
        })
    return probes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    import mlx.core as mx
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler
    probes = build_probes()
    result = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "scope": "Seven ad hoc withheld probes; qualitative review required; no automatic theological accuracy score.",
        "trainingUse": "None: evaluation prompts only",
        "generation": {"enableThinking": False, "temperature": 0.7, "topP": 0.8,
                       "topK": 20, "maxTokens": 220, "seed": 41},
        "probes": probes, "variants": {},
    }
    system = ("You are a comparative religious research assistant. Use only supplied evidence. "
              "Distinguish an author's assertions from quotations and surveys. Name sources and "
              "preserve disagreements. Do not prefer a religion or Christian tradition. "
              "Do not invent citations; admit missing evidence. Keep the answer brief.")
    variants = [("base", None)]
    if args.adapter:
        variants.append(("adapted", str(args.adapter)))
    for variant, adapter_path in variants:
        model, tokenizer = load(str(args.base), adapter_path=adapter_path)
        outputs = []
        for probe in probes:
            mx.random.seed(41)
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": "Evidence:\n" + probe["context"] + "\n\nQuestion: " + probe["question"]},
            ]
            prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                                                   add_generation_prompt=True, enable_thinking=False)
            started = time.monotonic()
            answer = generate(model, tokenizer, prompt=prompt, max_tokens=220,
                              sampler=make_sampler(temp=0.7, top_p=0.8, top_k=20), verbose=False)
            outputs.append({
                "probeId": probe["id"], "answer": answer,
                "seconds": round(time.monotonic() - started, 3),
                "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "outputTokens": len(tokenizer.encode(answer)),
            })
            print(f"{variant}: {probe['id']} ({outputs[-1]['seconds']}s)", flush=True)
        result["variants"][variant] = outputs
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        del model, tokenizer
        gc.collect()
        mx.clear_cache()


if __name__ == "__main__":
    main()
