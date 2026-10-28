"""Downloads the swisstopo swissBOUNDARIES3D GeoPackage (fixed release, see config maps.boundaries) and checks
its SHA-256 checksum."""
import hashlib
from pathlib import Path

import requests


def fetch(url: str, sha256: str, path: str) -> None:
    response = requests.get(url, timeout=600)
    response.raise_for_status()
    digest = hashlib.sha256(response.content).hexdigest()
    if digest != sha256.lower():
        raise ValueError(f"checksum mismatch for {url}: {digest} != {sha256}")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(response.content)


if __name__ == "__main__":
    fetch(snakemake.params.url, snakemake.params.sha256, snakemake.output[0])
