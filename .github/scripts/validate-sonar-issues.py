#!/usr/bin/env python3
"""Falha o build se o SonarCloud reportar issue ou security hotspot aberto.
--branch so aceita "main" (plano gratuito recusa outras branches, 403).

Uso:
    validate-sonar-issues.py --project-key eimmig_sv-telegram-integration-backend --pull-request 20
    validate-sonar-issues.py --project-key eimmig_sv-telegram-integration-backend --branch main

Espera SONAR_TOKEN no ambiente.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SONAR_API = "https://sonarcloud.io/api"
PAGE_SIZE = 500


def sonar_get(token: str, path: str) -> dict:
    request = urllib.request.Request(
        f"{SONAR_API}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        sys.exit(f"ERRO SonarCloud {error.code} em {path}: {error.reason}")
    except urllib.error.URLError as error:
        sys.exit(f"ERRO de rede ao falar com o SonarCloud: {error.reason}")


def paginate(token: str, endpoint: str, query: dict[str, str], items_key: str) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        result = sonar_get(token, f"{endpoint}?{urllib.parse.urlencode({**query, 'p': page, 'ps': PAGE_SIZE})}")
        page_items = result.get(items_key, [])
        items.extend(page_items)
        total = result.get("paging", {}).get("total", len(items))
        if len(items) >= total or not page_items:
            return items
        page += 1


def check_issues(token: str, project_key: str, scope: dict[str, str]) -> list[str]:
    query = {"componentKeys": project_key, "statuses": "OPEN,CONFIRMED,REOPENED", **scope}
    issues = paginate(token, "/issues/search", query, "issues")
    return [
        f"[{i['severity']}] {i['rule']} {i['component'].split(':')[-1]}:{i.get('line', '-')} - {i['message']}"
        for i in issues
    ]


def check_hotspots(token: str, project_key: str, scope: dict[str, str]) -> list[str]:
    query = {"projectKey": project_key, "status": "TO_REVIEW", **scope}
    hotspots = paginate(token, "/hotspots/search", query, "hotspots")
    return [
        f"[HOTSPOT] {h['ruleKey']} {h['component'].split(':')[-1]}:{h.get('line', '-')} - {h['message']}"
        for h in hotspots
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-key", required=True)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--pull-request")
    scope.add_argument("--branch")
    args = parser.parse_args()

    token = os.environ.get("SONAR_TOKEN")
    if not token:
        sys.exit("ERRO: SONAR_TOKEN nao definido no ambiente.")

    scope_param = {"pullRequest": args.pull_request} if args.pull_request else {"branch": args.branch}
    findings = check_issues(token, args.project_key, scope_param) + check_hotspots(token, args.project_key, scope_param)

    if not findings:
        print("OK   SonarCloud sem issues nem security hotspots abertos.")
        return

    print(f"FAIL SonarCloud reportou {len(findings)} apontamento(s):")
    for line in findings:
        print(f"     {line}")
    sys.exit(1)


if __name__ == "__main__":
    main()
