#!/usr/bin/env python3
"""Confere que os arquivos de traducao pt-BR/en-US/es tem exatamente o mesmo conjunto de
chaves. Ver docs/CI-CD.md secao "Os 5 passos" (passo 2) e docs/CONVENTIONS.md secao
"Internacionalizacao (i18n)" - os tres locales sempre em sincronia e requisito de `done`.

Uso:
    validate-i18n-keys.py --format properties \\
        --file pt-BR=services/auth-service/src/main/resources/messages_pt_BR.properties \\
        --file en-US=services/auth-service/src/main/resources/messages_en_US.properties \\
        --file es=services/auth-service/src/main/resources/messages_es.properties

    validate-i18n-keys.py --format json \\
        --file pt-BR=apps/web/src/assets/i18n/pt-BR.json \\
        --file en-US=apps/web/src/assets/i18n/en-US.json \\
        --file es=apps/web/src/assets/i18n/es.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_properties_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        for sep in ("=", ":"):
            if sep in line:
                keys.add(line.split(sep, 1)[0].strip())
                break
    return keys


def flatten_json_keys(value: object, prefix: str = "") -> set[str]:
    if isinstance(value, dict):
        keys: set[str] = set()
        for k, v in value.items():
            full_key = f"{prefix}.{k}" if prefix else k
            keys |= flatten_json_keys(v, full_key)
        return keys
    return {prefix} if prefix else set()


def parse_json_keys(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return flatten_json_keys(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--format", choices=["properties", "json"], required=True)
    parser.add_argument(
        "--file",
        action="append",
        required=True,
        metavar="LOCALE=PATH",
        help="repetir uma vez por locale, ex.: --file pt-BR=caminho/arquivo.json",
    )
    args = parser.parse_args()

    if len(args.file) < 2:
        print("FAIL preciso de pelo menos 2 arquivos de locale para comparar.")
        return 1

    parse_keys = parse_properties_keys if args.format == "properties" else parse_json_keys

    keys_by_locale: dict[str, set[str]] = {}
    for entry in args.file:
        if "=" not in entry:
            print(f"FAIL argumento invalido '{entry}', esperado LOCALE=PATH")
            return 1
        locale, raw_path = entry.split("=", 1)
        path = Path(raw_path)
        if not path.is_file():
            print(f"MISS arquivo de locale '{locale}' nao encontrado em {path}")
            return 1
        keys_by_locale[locale] = parse_keys(path)

    all_keys: set[str] = set()
    for keys in keys_by_locale.values():
        all_keys |= keys

    mismatch = False
    for locale, keys in keys_by_locale.items():
        missing = sorted(all_keys - keys)
        if missing:
            mismatch = True
            print(f"FAIL locale '{locale}' esta faltando {len(missing)} chave(s):")
            for key in missing:
                print(f"     - {key}")

    if mismatch:
        print("FAIL os arquivos de traducao nao estao em sincronia (ver docs/CONVENTIONS.md 'Internacionalizacao').")
        return 1

    print(f"OK   {len(all_keys)} chave(s) em sincronia entre {', '.join(keys_by_locale)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
