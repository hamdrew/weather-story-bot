"""Zip a directory into bytes that depend only on the files' names and contents.

`make build` uses this so the same source and lockfile always give the same zip, and so the same
sha256. Terraform's `source_code_hash` and the artifacts bucket key (Phase 2.1) are that hash, so a
rebuild that changes nothing plans as "No changes". Entries are sorted, carry no directory entries,
and have a fixed timestamp and mode, so mtimes, the order the files were written in and their modes
can't leak into the bytes.

Entries are stored, not deflated. Deflate's output depends on the zlib behind the interpreter
(Apple's, zlib-ng, vanilla), so a laptop and a CI runner could disagree on the bytes. The package is
a couple of MB, far under Lambda's 50 MB limit. One input is still outside this script: the
`*.dist-info/RECORD` and `INSTALLER` files that `uv pip install` writes, which can vary with the uv
version, so keep CI's uv version the same as the laptop's.

Standard library only: the credentialed CI jobs run it with `uv run --no-project`, so no
third-party code runs beside AWS credentials.

    uv run --no-project python scripts/build_zip.py build/package build/lambda.zip

Prints the zip's base64 sha256 (the form Terraform's `filebase64sha256` uses) and nothing else.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import zipfile
from pathlib import Path

# The earliest timestamp a zip can hold.
FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
# A regular file, rw-r--r--. Lambda's Python runtime needs no executable bits.
FIXED_ATTRIBUTES = 0o100644 << 16


def build_zip(source: Path, destination: Path) -> str:
    """Write `source`'s files to `destination` and return the zip's base64 sha256.

    That is the raw 32-byte SHA-256 digest of the zip's bytes, base64-encoded (RFC 4648 section 4,
    padded), exactly what Terraform's `filebase64sha256(path)` returns. It is hashed from the
    file as written, not from memory, so it matches the artifact that gets uploaded. It is not the
    hex digest.

    https://developer.hashicorp.com/terraform/language/functions/filebase64sha256
    https://developer.hashicorp.com/terraform/language/functions/base64sha256 (the encoding)
    https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function
    (`source_code_hash` takes this value and triggers an update when it changes)
    """
    names = []
    for path in source.rglob("*"):
        # rglob doesn't follow a symlinked directory, so its files would silently be left out.
        if path.is_symlink() and path.is_dir():
            raise ValueError(
                f"{path} is a symlink to a directory, which would be left out of the zip"
            )
        if path.is_file():
            names.append(path.relative_to(source).as_posix())
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_STORED) as archive:
        for name in sorted(names):
            info = zipfile.ZipInfo(name, FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = FIXED_ATTRIBUTES
            archive.writestr(info, (source / name).read_bytes())
    return base64.b64encode(hashlib.sha256(destination.read_bytes()).digest()).decode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="directory to zip")
    parser.add_argument("destination", type=Path, help="zip file to write")
    args = parser.parse_args(argv)
    print(build_zip(args.source, args.destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
