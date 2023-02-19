from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pydantic import BaseModel
from pydealer import (  # type: ignore
    Card,
    Stack,
)


class RequestType(Enum):
    SET_TABLE_CARDS = 1
    PLAY = 2


@dataclass
class TableStack:
    bottom_card: Card
    top_card: Optional[Card] = None


@dataclass
class Hand:
    table_stacks: list[TableStack] = field(default_factory=list)
    hand_stack: Stack = Stack()


class Action(Enum):
    SET_TABLE_CARDS = 0
    PLAY_FACE_DOWN = 1
    PLAY_FACE_UP = 2
    PLAY_FROM_HAND = 3
    PICK_UP_DISCARD_PILE = 4
    PLAY_KNOWN_CARDS = 5


@dataclass
class Play:
    action: Action
    cards: Optional[Stack] = None


class UpdateType(Enum):
    GAME_INITIATED = 100
    DECK_DEPLETED = 101
    PLAYER_WINS = 102
    YOU_DREW_CARD = 200
    PLAYER_DREW_CARD = 201
    YOU_PICKED_UP_DISCARD_PILE = 300
    PLAYER_PICKED_UP_DISCARD_PILE = 301
    BURN_DISCARD_PILE = 302
    PLAY_FROM_HAND = 401
    PLAY_FROM_TABLE = 402
    PLAY_FROM_FACEDOWN_SUCCESS = 403
    PLAY_FROM_FACEDOWN_FAILURE = 404
    PLAY_FROM_FACEUP_FAILURE = 405
    SET_TABLE_CARDS = 500
    INVALID_ACTION = 700


class Update(BaseModel):
    update_type: UpdateType
    player_number: Optional[int] = None
    cards: Optional[str] = None
    number_of_players: Optional[int] = None
    message: Optional[str] = None


class Response(BaseModel):
    action: Action
    cards: Optional[str] = None
