from __future__ import annotations

import re
from dataclasses import dataclass

_AMOUNT = r"(\d+(?:[.,]\d{1,2})?)"
_ODD = r"(\d{1,3}[.,]\d{2})"
_NOT_DIGIT = r"(?![\d])"
_NOT_AFTER_NUMBER = r"(?<![\d.,])"
# Valor apostado, em ordem de prioridade (feat-017 e feat-019): moeda antes ("R$ 50", "BRL 50,00",
# "$12"), palavra-chave antes ("stake 5,00", "valor: 10", "aposta de 20", "apostei 100",
# "valendo 30") ou depois ("50 reais", "20 conto", "25,00 de stake", "12.50$").
_STAKE_PATTERNS = (
    re.compile(r"(?:R\$|(?<![\d.,])\$|\bBRL)\s*" + _AMOUNT + _NOT_DIGIT, re.IGNORECASE),
    re.compile(r"\b(?:stake|valor|aposta\s+de|apostei|valendo)\s*(?:de\s*|:\s*|=\s*)?" + _AMOUNT + _NOT_DIGIT,
               re.IGNORECASE),
    re.compile(_NOT_AFTER_NUMBER + _AMOUNT + r"\s*(?:(?:reais|contos?|de\s+stake)\b|\$|BRL\b)", re.IGNORECASE),
)
# Odd com marca explicita: palavra-chave antes ("odd 1.85", "odds 2,10", "cotacao: 1.90", "pagando 2.05"),
# arroba ("@2.35"), "x" colado ("x1,72", "4,75x") ou "de odd" depois ("1,23 de odd").
_ODD_MARKED_PATTERNS = (
    # "de odd" depois vem primeiro: em "1,23 de odd 12.50$", a odd e o numero antes da palavra
    re.compile(_NOT_AFTER_NUMBER + _ODD + r"\s*de\s+odd\b", re.IGNORECASE),
    re.compile(r"(?:\bodds?|cota[cç][aã]o|pagando)\D{0,10}?" + _ODD, re.IGNORECASE),
    re.compile(r"@\s*" + _ODD),
    re.compile(r"(?<![\w.,])x\s*" + _ODD + _NOT_DIGIT, re.IGNORECASE),
    re.compile(_NOT_AFTER_NUMBER + _ODD + r"x\b", re.IGNORECASE),
)
# A odd solta nao pode vir colada em outro numero, mas pode vir seguida de virgula ou ponto
# de pontuacao ("3.88, pela pixbet"; "odd 1.90.").
_BARE_ODD_PATTERN = re.compile(_NOT_AFTER_NUMBER + _ODD + r"(?!\d|[.,]\d)")

_KNOWN_BETTING_HOUSES = (
    "Bet365",
    "Betano",
    "Sportingbet",
    "KTO",
    "Betfair",
    "Betnacional",
    "Pixbet",
    "Novibet",
    "Stake",
    "Vupi",
)

REQUIRED_FIELDS = ("odd", "stake")


@dataclass
class ExtractedBet:
    odd: str | None = None
    stake: str | None = None
    bet_date: str | None = None
    betting_house: str | None = None
    sport: str | None = None
    league: str | None = None
    market: str | None = None
    team1: str | None = None
    team2: str | None = None

    def missing_required_fields(self) -> list[str]:
        return [name for name in REQUIRED_FIELDS if getattr(self, name) is None]


def _without_stakes(text: str) -> str:
    for pattern in _STAKE_PATTERNS:
        text = pattern.sub(" ", text)
    return text


def _extract_odd(text: str) -> str | None:
    for pattern in _ODD_MARKED_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).replace(",", ".")
    # Sem marca, a odd e o unico decimal que sobra depois de tirar os valores apostados. Se sobra
    # mais de um valor diferente, nao ha como saber qual e a odd, e o bot pergunta (feat-019): antes,
    # o primeiro numero era aceito, e um valor apostado escrito de forma nao prevista virava odd.
    candidates = set()
    for candidate in _BARE_ODD_PATTERN.finditer(_without_stakes(text)):
        value = float(candidate.group(1).replace(",", "."))
        if 1.01 <= value <= 1000:
            candidates.add(f"{value:.2f}")
    return candidates.pop() if len(candidates) == 1 else None


def _extract_stake(text: str) -> str | None:
    for pattern in _STAKE_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return match.group(1).replace(",", ".")
    return None


def _extract_betting_house(text: str) -> str | None:
    # Sem os valores ("stake 5,00" nao e a casa Stake) e sem espacos, para aceitar "bet 365".
    compact = re.sub(r"\s+", "", _without_stakes(text).lower())
    for house in _KNOWN_BETTING_HOUSES:
        if house.lower() in compact:
            return house
    return None


_BARE_NUMBER_PATTERN = re.compile(r"\d{1,3}[.,]\d{1,2}|\d+")


def parse_direct_answer(field: str, text: str) -> str:
    stripped = text.strip()
    if field in ("odd", "stake"):
        match = _BARE_NUMBER_PATTERN.search(stripped)
        return match.group(0).replace(",", ".") if match else stripped
    return stripped


def extract_fields(text: str) -> ExtractedBet:
    return ExtractedBet(
        odd=_extract_odd(text),
        stake=_extract_stake(text),
        betting_house=_extract_betting_house(text),
    )
