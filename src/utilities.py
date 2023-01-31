from collections import Counter
from typing import Optional

from pydealer import (  # type: ignore
    Card,
    Stack,
    VALUES,
)

from src.constants import (
    DECODE_SUIT,
    DECODE_VALUE,
    ENCODE_SUIT,
    ENCODE_VALUE,
)
from src.exceptions import CardEncodeDecodeException
from src.game_types import Action, Hand, Play, Response, TableStack


def are_all_cards_same_value(stack: Stack) -> bool:

    if len(stack) == 0:
        raise Exception("Cannot check values of empty")

    return len(set([card.value for card in stack])) == 1


def does_play_trump_last_play(cards_played: Stack, last_play: Optional[Stack]) -> bool:

    if last_play is None:
        return True

    if len(cards_played) < len(last_play):
        return False

    return cards_played[0] >= last_play[0]


def card_set_from_stack(stack: Stack) -> set[tuple[str, str]]:

    return set((card.value, card.suit) for card in stack)


def convert_response_to_play(response: Response) -> Play:

    play = Play(action=response.action)

    if response.action == Action.PLAY_KNOWN_CARDS:
        assert response.cards
        cards = deserialize_cards(encoded_cards=response.cards)
        assert len(cards)
        play.cards = cards

    return play


def deserialize_cards(encoded_cards: str) -> Stack:

    if len(encoded_cards) == 0:
        return Stack()

    card_codes = encoded_cards.split(",")

    decoded_cards = []

    for card_code in card_codes:
        decoded_cards.append(deserialize_card(card_code))

    return Stack(cards=decoded_cards)


def deserialize_card(card_code: str) -> Card:

    if len(card_code) != 2:
        raise CardEncodeDecodeException("Card code not valid")

    if card_code[0] not in DECODE_SUIT:
        raise CardEncodeDecodeException("Card code not valid")

    if card_code[1] not in DECODE_VALUE:
        raise CardEncodeDecodeException("Card code not valid")

    value = DECODE_VALUE[card_code[1]]
    suit = DECODE_SUIT[card_code[0]]

    return Card(value=value, suit=suit)


def serialize_cards(cards: Stack) -> str:

    serialized_cards = []

    for card in cards.cards:
        serialized_cards.append(serialize_card(card))

    return ",".join(serialized_cards)


def serialize_card(card: Card) -> str:
    card_name = card.name
    suit, value = split_card_name(card_name=card_name)

    return ENCODE_SUIT[suit] + ENCODE_VALUE[value]


def split_card_name(card_name: str) -> tuple[str, str]:

    value: str

    value, suit = card_name.split(" of ")

    return suit, value


def build_face_up_table_stack(table_stacks: list[TableStack]) -> Stack:

    face_up_table_stack = Stack(
        cards=[
            table_stack.top_card
            for table_stack in table_stacks
            if table_stack.top_card is not None
        ]
    )

    return face_up_table_stack


def is_play_available(hand: Hand, last_play: Stack, played_cards: Stack) -> bool:
    available_plays = get_available_plays_from_hand(hand=hand, last_play=last_play)
    return (played_cards[0].value, len(played_cards)) in available_plays


def get_available_plays_from_hand(hand: Hand, last_play: Stack) -> set[tuple["str", "int"]]:

    if len(hand.hand_stack):
        return get_available_plays_from_stack(stack=hand.hand_stack, last_play=last_play)
    elif len(hand.table_stacks):
        return get_available_plays_from_stack(
            stack=build_face_up_table_stack(hand.table_stacks), last_play=last_play
        )
    else:
        return set()


def get_available_plays_from_stack(stack: Stack, last_play: Stack) -> set[tuple["str", "int"]]:

    available_plays: set[tuple["str", "int"]] = set()

    value_order = {VALUES[i]: i for i in range(len(VALUES)) if VALUES[i] not in ["2", "10"]}

    if last_play is None or last_play[0].value == "2" or last_play[0].value == "10":
        last_play_order = value_order["3"]
        last_play_count = 1
    else:
        last_play_order = value_order[last_play[0].value]
        last_play_count = len(last_play)

    for card in stack:
        if card.value in ["2", "10"]:
            available_plays.add((card.value, 1))

    value_counter = Counter([card.value for card in stack if card.value in value_order.keys()])

    for value, count in value_counter.items():
        if value_order[value] >= last_play_order and count >= last_play_count:
            for i in range(last_play_count, count + 1):
                available_plays.add((value, i))

    return available_plays


def do_face_up_table_cards_exist(table_stacks: list[TableStack]) -> bool:
    for table_stack in table_stacks:
        if table_stack.top_card is not None:
            return True

    return False


def count_player_cards(hand: Hand) -> int:
    count = len(hand.hand_stack)
    for table_stack in hand.table_stacks:
        if table_stack.top_card is not None:
            count += 2
        else:
            count += 1
    return count
