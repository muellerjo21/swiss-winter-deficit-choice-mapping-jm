"""Downloads one source file (GET or POST, params.method). With params.sha256 the SHA-256 checksum of the file must
match; without it (exports generated on request, not byte-stable) the file must be a non-empty xlsx (zip) file and
its content is checked by the rule that reads it."""
import hashlib
from pathlib import Path

import requests


def fetch(url: str, path: str, method: str = "get", sha256: str = None) -> None:
    response = requests.request(method.upper(), url, timeout=600)
    response.raise_for_status()
    content = response.content
    if sha256:
        digest = hashlib.sha256(content).hexdigest()
        if digest != sha256.lower():
            raise ValueError(f"checksum mismatch for {url}: {digest} != {sha256}")
    elif not content.startswith(b"PK"):
        raise ValueError(f"{url} did not return an xlsx file ({len(content)} bytes)")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(content)


if __name__ == "__main__":
    p = snakemake.params
    fetch(p.url, snakemake.output[0], p.method, p.sha256)
