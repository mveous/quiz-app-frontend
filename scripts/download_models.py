"""One-time setup: download the GGUF model files Shali v1 (ShaliProvider) needs.

Run once from the backend/ directory:

    python scripts/download_models.py

Downloads land in backend/models/ (gitignored — binary, several GB) and are
reused on every future run; already-downloaded files are skipped.
"""

from pathlib import Path

from huggingface_hub import hf_hub_download

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

MODELS = [
    {
        "repo_id": "bartowski/Qwen2.5-7B-Instruct-GGUF",
        "filename": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "purpose": "generation",
    },
    {
        "repo_id": "nomic-ai/nomic-embed-text-v1.5-GGUF",
        "filename": "nomic-embed-text-v1.5.Q4_K_M.gguf",
        "purpose": "embedding",
    },
]


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for model in MODELS:
        destination = MODELS_DIR / model["filename"]
        if destination.exists():
            print(f"[skip] {model['purpose']} model already present: {destination}")
            continue
        print(f"[download] {model['purpose']} model: {model['repo_id']}/{model['filename']}")
        downloaded_path = hf_hub_download(
            repo_id=model["repo_id"],
            filename=model["filename"],
            local_dir=MODELS_DIR,
        )
        print(f"[done] saved to {downloaded_path}")


if __name__ == "__main__":
    main()
