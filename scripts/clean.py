"""Removes all build results (rule clean). build may be a symlink to build.nosync/ (outside the iCloud sync): its
content is emptied, the link is kept. Data in data/ (incl. the frozen references in data/processed/) stays."""
import shutil
from pathlib import Path

if __name__ == "__main__":
    build = Path("build")
    for item in (build.resolve().iterdir() if build.exists() else []):
        shutil.rmtree(item) if item.is_dir() and not item.is_symlink() else item.unlink()
    print("Data in data/ (incl. frozen references in data/processed/) has not been cleaned.")
