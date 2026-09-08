from telegram_integration.extraction import ExtractedBet, extract_fields, parse_direct_answer


def test_extracts_odd_near_the_odd_keyword() -> None:
    result = extract_fields("Flamengo x Corinthians\nOdd: 1.85\nCasa: Bet365")

    assert result.odd == "1.85"


def test_extracts_odd_with_comma_decimal_separator() -> None:
    result = extract_fields("odd 2,50")

    assert result.odd == "2.50"


def test_extracts_stake_prefixed_by_currency() -> None:
    result = extract_fields("Valor apostado: R$ 50,00")

    assert result.stake == "50.00"


def test_extracts_date_in_dd_mm_yyyy_format() -> None:
    result = extract_fields("Aposta feita em 08/09/2026")

    assert result.bet_date == "2026-09-08"


def test_extracts_date_with_two_digit_year() -> None:
    result = extract_fields("08/09/26")

    assert result.bet_date == "2026-09-08"


def test_extracts_known_betting_house_by_name() -> None:
    result = extract_fields("Comprovante Bet365 - aposta simples")

    assert result.betting_house == "Bet365"


def test_returns_all_none_for_unrecognizable_garbled_text() -> None:
    result = extract_fields("###   asdkjh ///")

    assert result == ExtractedBet()


def test_never_guesses_sport_league_market_or_teams() -> None:
    result = extract_fields("Flamengo x Corinthians, Brasileirao, over 2.5 gols, futebol, odd 1.85")

    assert result.sport is None
    assert result.league is None
    assert result.market is None
    assert result.team1 is None
    assert result.team2 is None


def test_missing_required_fields_lists_only_unresolved_ones() -> None:
    result = ExtractedBet(odd="1.85", stake=None, bet_date="2026-09-08")

    assert result.missing_required_fields() == ["stake"]


def test_missing_required_fields_empty_when_everything_required_is_set() -> None:
    result = ExtractedBet(odd="1.85", stake="50.00", bet_date="2026-09-08")

    assert result.missing_required_fields() == []


def test_parse_direct_answer_reads_bare_stake_without_currency_prefix() -> None:
    # A direct reply to "how much did you stake?" is unlikely to include R$/$
    # even though extract_fields requires that prefix when scanning free text.
    assert parse_direct_answer("stake", "50") == "50"


def test_parse_direct_answer_reads_bare_odd_without_a_keyword() -> None:
    assert parse_direct_answer("odd", "1.85") == "1.85"


def test_parse_direct_answer_normalizes_comma_decimal_separator() -> None:
    assert parse_direct_answer("stake", "50,00") == "50.00"


def test_parse_direct_answer_normalizes_the_date_to_iso() -> None:
    assert parse_direct_answer("bet_date", "08/09/2026") == "2026-09-08"


def test_parse_direct_answer_falls_back_to_raw_text_when_unparseable() -> None:
    assert parse_direct_answer("bet_date", "sometime next week") == "sometime next week"


def test_parse_direct_answer_returns_raw_text_for_a_free_text_field() -> None:
    assert parse_direct_answer("betting_house", "Bet365") == "Bet365"
