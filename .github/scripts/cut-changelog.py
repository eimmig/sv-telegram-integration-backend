#!/usr/bin/env python3

import datetime
import pathlib
import sys

if len(sys.argv) != 3:
    sys.exit("uso: cut-changelog.py <CHANGELOG.md> <versao ex: 1.2.0>")

path = pathlib.Path(sys.argv[1])
version = sys.argv[2]
date = datetime.date.today().isoformat()
marker = "## [Unreleased]"

text = path.read_text(encoding="utf-8")
if marker not in text:
    sys.exit(f"FAIL {marker} nao encontrado em {path}")

new_text = text.replace(marker, f"{marker}\n\n## [{version}] - {date}", 1)
path.write_text(new_text, encoding="utf-8")
print(f"OK {path}: novo {marker} aberto, secao anterior renomeada para [{version}] - {date}")
