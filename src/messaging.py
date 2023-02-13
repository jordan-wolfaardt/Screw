import json
from multiprocessing.connection import Connection
from typing import Optional

from pydealer import (  # type: ignore
    Card,
    Stack,
)

from src.game_types import RequestType, Response, Update, UpdateType
from src.utilities import serialize_card, serialize_cards


class Messaging:
    def __init__(
        self,
        number_of_players: int,
        connection: Connection,
    ) -> None:

        self.number_of_players = number_of_players
        self.connection = connection
        return

    def game_initiated(self) -> None:
        update = Update(update_type=UpdateType.GAME_INITIATED)
        self.update_players(update=update)
        return

    def deck_depleted(self) -> None:
        update = Update(update_type=UpdateType.DECK_DEPLETED)
        self.update_players(update=update)
        return

    def player_wins(self, player_number: int) -> None:
        update = Update(update_type=UpdateType.PLAYER_WINS, player_number=player_number)
        self.update_players(update=update)
        return

    def card_draw(self, player_number: int, card: Card) -> None:
        self.you_drew_card(player_number=player_number, card=card)
        self.player_drew_card(player_number=player_number)
        return

    def you_drew_card(self, player_number: int, card: Card) -> None:
        serialized_card = serialize_card(card=card)
        update = Update(update_type=UpdateType.YOU_DREW_CARD, cards=serialized_card)
        self.update_player(player_number=player_number, update=update)
        return

    def player_drew_card(self, player_number: int) -> None:
        update = Update(
            update_type=UpdateType.PLAYER_DREW_CARD,
            player_number=player_number,
        )
        self.update_players(update=update, exclude_player=player_number)
        return

    def discard_pile_pickup(self, player_number: int, cards: Stack) -> None:
        self.you_picked_up_discard_pile(player_number=player_number, cards=cards)
        self.player_picked_up_discard_pile(player_number=player_number)
        return

    def you_picked_up_discard_pile(self, player_number: int, cards: Stack) -> None:
        update = Update(
            update_type=UpdateType.YOU_PICKED_UP_DISCARD_PILE,
            cards=serialize_cards(cards=cards),
        )
        self.update_player(player_number=player_number, update=update)
        return

    def burn_discard_pile(self) -> None:
        update = Update(
            update_type=UpdateType.BURN_DISCARD_PILE,
        )
        self.update_players(update=update)
        return

    def player_picked_up_discard_pile(self, player_number: int) -> None:
        update = Update(
            update_type=UpdateType.PLAYER_PICKED_UP_DISCARD_PILE,
            player_number=player_number,
        )
        self.update_players(update=update, exclude_player=player_number)
        return

    def play_from_hand(self, player_number: int, cards: Stack) -> None:
        update = Update(
            update_type=UpdateType.PLAY_FROM_HAND,
            cards=serialize_cards(cards=cards),
            player_number=player_number,
        )
        self.update_players(update=update)

        return

    def play_from_table(self, player_number: int, cards: Stack) -> None:
        update = Update(
            update_type=UpdateType.PLAY_FROM_TABLE,
            cards=serialize_cards(cards=cards),
            player_number=player_number,
        )
        self.update_players(update=update)

        return

    def play_from_facedown_success(self, player_number: int, card: Card) -> None:
        update = Update(
            update_type=UpdateType.PLAY_FROM_FACEDOWN_SUCCESS,
            cards=serialize_card(card=card),
            player_number=player_number,
        )
        self.update_players(update=update)

        return

    def play_from_facedown_failure(self, player_number: int, card: Card) -> None:
        update = Update(
            update_type=UpdateType.PLAY_FROM_FACEDOWN_FAILURE,
            cards=serialize_card(card=card),
            player_number=player_number,
        )
        self.update_players(update=update)

        return

    def play_from_faceup_failure(self, player_number: int, cards: Stack) -> None:
        update = Update(
            update_type=UpdateType.PLAY_FROM_FACEUP_FAILURE,
            cards=serialize_cards(cards=cards),
            player_number=player_number,
        )
        self.update_players(update=update)

        return

    def set_table_cards(self, player_number: int, cards: Stack) -> None:
        update = Update(
            update_type=UpdateType.SET_TABLE_CARDS,
            cards=serialize_cards(cards=cards),
            player_number=player_number,
        )
        self.update_players(update=update)

        return

    def invalid_action(self, player_number: int, message: str) -> None:
        update = Update(update_type=UpdateType.INVALID_ACTION, message=message)
        self.update_player(player_number=player_number, update=update)
        return

    def update_players(self, update: Update, exclude_player: Optional[int] = None) -> None:
        for player_number in range(self.number_of_players):
            if player_number != exclude_player:
                self.update_player(player_number=player_number, update=update)
        return

    def update_player(self, player_number: int, update: Update) -> None:

        update_json = update.json()
        body_dict = dict(
            type="update",
            recipient=player_number,
            update=update_json,
        )

        body = json.dumps(body_dict)

        self.update(body=body)

        return

    def request(self, player_number: int, request_type: RequestType) -> Response:

        body_dict = dict(
            type="request",
            recipient=player_number,
            request_type=request_type.name,
        )

        body = json.dumps(body_dict)

        serialized_response = self.update(body=body)

        return Response.parse_raw(serialized_response)

    def update(self, body: str) -> str:

        self.connection.send(body)
        response = self.connection.recv()
        return response
