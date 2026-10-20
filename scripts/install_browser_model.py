#!/usr/bin/env python3
"""Install the checksum-pinned browser model into a static Pages build."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Use a local release archive instead of downloading.")
    args = parser.parse_args()
    release = json.loads((ROOT / "model-release.json").read_text())
    destination = ROOT / "dist/models/scripture-qwen3-0.6b-v2/resolve/v2"
    if not (ROOT / "dist/index.html").is_file():
        raise SystemExit("Build the app before installing the model.")
    with tempfile.TemporaryDirectory(prefix="scripture-model-") as temporary:
        temporary = Path(temporary)
        archive = args.archive or temporary / "model.tar.gz"
        if not args.archive:
            with urllib.request.urlopen(release["url"], timeout=120) as response, archive.open("wb") as output:
                shutil.copyfileobj(response, output)
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != release["sha256"] or archive.stat().st_size != release["bytes"]:
            raise SystemExit("Model archive failed checksum or size verification.")
        extracted = temporary / "extracted"
        with tarfile.open(archive, "r:gz") as bundle:
            members = bundle.getmembers()
            if sum(m.size for m in members) >= 1_000_000_000:
                raise SystemExit("Model package exceeds 1 GB.")
            for member in members:
                path = Path(member.name)
                if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                    raise SystemExit("Unsafe model archive member.")
                if not path.parts or path.parts[0] != release["directory"]:
                    raise SystemExit("Unexpected model archive layout.")
            bundle.extractall(extracted, filter="data")
        source = extracted / release["directory"]
        for name in ("mlc-chat-config.json", "tensor-cache.json", "tokenizer.json", "LICENSE"):
            if not (source / name).is_file():
                raise SystemExit(f"Missing required model artifact: {name}")
        cache = json.loads((source / "tensor-cache.json").read_text())
        for shard in cache["records"]:
            path = source / shard["dataPath"]
            if path.parent != source or not path.is_file() or path.stat().st_size != shard["nbytes"]:
                raise SystemExit("Invalid or missing weight shard.")
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, dirs_exist_ok=True)
        print(f"Installed {release['id']}: verified {archive.stat().st_size:,} archive bytes.")


if __name__ == "__main__":
    main()
