"""Download the integrity detector model once, pinned to a verified revision:

    python -m scripts.download_integrity_model [target_dir]

Then set AI_INTEGRITY_MODEL_PATH to the printed directory. After this the app needs no network.
See docs/integrity/MODEL_VERIFICATION.md.
"""
import sys
from pathlib import Path

REPO = "rasbt/ai-text-detector-modernbert"
REVISION = "a6efd4bf6ecd852f332b2569ae0f98cae13b7985"   # verified 2026-10-18
FILES = ["config.json", "detector-config.json", "model.safetensors", "tokenizer.json",
         "tokenizer_config.json", "LICENSE", "README.md"]
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "models" / "ai-text-detector-modernbert"


def download(target: Path = DEFAULT_DIR) -> Path:
    from huggingface_hub import snapshot_download
    path = Path(snapshot_download(REPO, revision=REVISION, local_dir=str(target), allow_patterns=FILES))
    (path / "REVISION").write_text(REVISION, encoding="utf-8")
    from app.nlp.ai_authorship import verify_label_mapping
    ai_index = verify_label_mapping(path)   # refuses to finish if the label mapping isn't explicit
    print(f"Downloaded {REPO}@{REVISION[:12]} to {path} (AI class index {ai_index})")
    print(f"Set AI_INTEGRITY_MODEL_PATH={path}")
    return path


if __name__ == "__main__":
    download(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR)
