from telegram_integration.extraction import ExtractedBet, extract_fields, parse_direct_answer


def test_extracts_odd_near_the_odd_keyword() -> None:
    result = extract_fields("Flamengo x Corinthians\nOdd: 1.85\nCasa: Bet365")

    assert result.odd == "1.85"


def test_extracts_odd_with_comma_decimal_separator() -> None:
    result = extract_fields("odd 2,50")

    assert result.odd == "2.50"


def test_extracts_odd_via_at_symbol_notation() -> None:
    result = extract_fields("Vinicius Jr (Real Madrid) @2.35")

    assert result.odd == "2.35"


def test_extracts_odd_ignoring_currency_prefixed_amounts() -> None:
    result = extract_fields("Valor Total R$2.50\nMais de 9.5 Escanteios 5.50")

    assert result.odd == "5.50"


def test_extracts_stake_prefixed_by_currency() -> None:
    result = extract_fields("Valor apostado: R$ 50,00")

    assert result.stake == "50.00"


def test_extracts_known_betting_house_by_name() -> None:
    result = extract_fields("Comprovante Bet365 - aposta simples")

    assert result.betting_house == "Bet365"


def test_does_not_extract_bet_date_from_text() -> None:
    result = extract_fields("Aposta feita em 08/09/2026")

    assert result.bet_date is None


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
    result = ExtractedBet(odd="1.85", stake=None)

    assert result.missing_required_fields() == ["stake"]


def test_missing_required_fields_empty_when_everything_required_is_set() -> None:
    result = ExtractedBet(odd="1.85", stake="50.00")

    assert result.missing_required_fields() == []


def test_parse_direct_answer_reads_bare_stake_without_currency_prefix() -> None:
    assert parse_direct_answer("stake", "50") == "50"


def test_parse_direct_answer_reads_bare_odd_without_a_keyword() -> None:
    assert parse_direct_answer("odd", "1.85") == "1.85"


def test_parse_direct_answer_normalizes_comma_decimal_separator() -> None:
    assert parse_direct_answer("stake", "50,00") == "50.00"


def test_parse_direct_answer_returns_raw_text_for_a_free_text_field() -> None:
    assert parse_direct_answer("betting_house", "Bet365") == "Bet365"


def test_extracts_stake_written_with_reais_after_the_amount() -> None:
    result = extract_fields("Flamengo x Palmeiras @1.85 50 reais na Betano")

    assert result.stake == "50"


def test_extracts_stake_after_the_valor_keyword() -> None:
    result = extract_fields("casa pixbet, valor 5,00, ambas marcam, odd 2.10")

    assert result.stake == "5.00"


def test_extracts_stake_after_apostei() -> None:
    result = extract_fields("Sinner x Alcaraz, apostei 100 na 1.90")

    assert result.stake == "100"


def test_currency_prefixed_stake_wins_over_the_other_forms() -> None:
    result = extract_fields("valor total R$ 12,50, possivel retorno 40 reais")

    assert result.stake == "12.50"


def test_extracts_bare_odd_followed_by_a_comma() -> None:
    result = extract_fields("R$ 12,50, Flamengo x Palmeiras, 3.88, pela pixbet")

    assert result.odd == "3.88"


def test_extracts_odd_at_the_end_of_a_sentence() -> None:
    result = extract_fields("Brasil x Argentina, odd 1.90.")

    assert result.odd == "1.90"


def test_does_not_take_a_valor_amount_as_the_odd() -> None:
    result = extract_fields("Gremio x Inter pela Betano valor 25,00 mais de 2.5 gols 4,75x")

    assert result.odd == "4.75"
    assert result.stake == "25.00"


def test_extracts_betting_house_written_with_spaces() -> None:
    assert extract_fields("na bet 365, odd 2.00").betting_house == "Bet365"
    assert extract_fields("na sporting bet, odd 2.00").betting_house == "Sportingbet"
