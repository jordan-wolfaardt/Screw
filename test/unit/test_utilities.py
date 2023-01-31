import pytest

from src.utilities import (
    are_all_cards_same_value,
    deserialize_cards,
    does_play_trump_last_play,
)


@pytest.mark.parametrize(
    "encoded_cards,expected",
    [
        ("H4,S4,D4", True),
        ("H4,S3", False),
    ],
)
def test_are_all_cards_same_value(encoded_cards: str, expected: bool) -> None:

    stack = deserialize_cards(encoded_cards=encoded_cards)

    assert are_all_cards_same_value(stack=stack) == expected


@pytest.mark.parametrize(
    "encoded_cards,encoded_last_play,expected",
    [
        ("H4", "H3", True),
        ("H5,D5", "S4,D4", True),
        ("H4", "S3,D3", False),
        ("H4,D4", "D5", False),
        ("H4,D4", None, True),
    ],
)
def test_does_play_trump_last_play(
    encoded_cards: str, encoded_last_play: str, expected: bool
) -> None:
    cards_played = deserialize_cards(encoded_cards=encoded_cards)

    if encoded_last_play is not None:
        last_play = deserialize_cards(encoded_cards=encoded_last_play)
    else:
        last_play = None

    assert does_play_trump_last_play(cards_played=cards_played, last_play=last_play) == expected
