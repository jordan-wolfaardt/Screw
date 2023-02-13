from itertools import combinations
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


def is_play_available(
    hand: Hand, last_play: Optional[Stack], cards_played: Stack, discard_pile: Stack
) -> bool:
    available_plays = get_available_plays_from_hand(
        hand=hand, last_play=last_play, discard_pile=discard_pile
    )
    cards_played.sort()
    return serialize_cards(cards=cards_played) in available_plays


def get_available_plays_from_hand(
    hand: Hand, last_play: Optional[Stack], discard_pile: Stack
) -> set[str]:

    if len(hand.hand_stack):
        play_from = hand.hand_stack
    elif len(hand.table_stacks):
        play_from = build_face_up_table_stack(hand.table_stacks)
    else:
        return set()

    return get_available_plays_from_stack(
        stack=play_from, last_play=last_play, discard_pile=discard_pile
    )


def get_available_plays_from_stack(
    stack: Stack, last_play: Optional[Stack], discard_pile: Stack
) -> set[str]:

    stack.sort()

    cards_by_value: dict[str, list[Card]] = {}

    for card in stack:
        if card.value in cards_by_value:
            cards_by_value[card.value].append(card)
        else:
            cards_by_value[card.value] = [card]

    available_plays: set[str] = set()

    value_order = {VALUES[i]: i for i in range(len(VALUES))}

    if last_play is None:
        last_play_order = value_order["2"]
        last_play_count = 1
    else:
        last_play_order = value_order[last_play[0].value]
        last_play_count = len(last_play)

    for value, cards in cards_by_value.items():
        if value in ["2", "10"]:
            for card in cards:
                available_plays.add(serialize_card(card=card))
        elif (
            len(cards) < 4
            and len(discard_pile) >= (4 - len(cards))
            and are_all_cards_same_value(
                stack=Stack(cards=cards) + discard_pile[(-4 + len(cards)) :]  # noqa: E203
            )
        ):
            card_stack = Stack(cards=cards)
            card_stack.sort()
            serialized_cards = serialize_cards(cards=card_stack)
            available_plays.add(serialized_cards)
        elif value_order[value] >= last_play_order and len(cards) >= last_play_count:
            for length in range(last_play_count, len(cards) + 1):
                for card_combination in combinations(cards, length):
                    card_combination_stack = Stack(cards=card_combination)
                    card_combination_stack.sort()
                    serialized_cards = serialize_cards(cards=card_combination_stack)
                    available_plays.add(serialized_cards)

    return available_plays


def count_player_cards(hand: Hand) -> int:
    count = len(hand.hand_stack)
    for table_stack in hand.table_stacks:
        if table_stack.top_card is not None:
            count += 2
        else:
            count += 1
    return count


def does_hand_have_known_cards(hand: Hand) -> bool:
    hand_cards_exist = len(hand.hand_stack) > 0
    face_up_cards_exist = len(build_face_up_table_stack(table_stacks=hand.table_stacks)) > 0
    known_cards_exist = hand_cards_exist or face_up_cards_exist
    return known_cards_exist
