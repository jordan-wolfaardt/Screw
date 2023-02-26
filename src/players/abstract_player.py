import json
import logging
from abc import ABC, abstractmethod

import zmq

from src.game_types import Update
from src.player_state import PlayerState
from src.utilities import get_available_plays_from_stack

logger = logging.getLogger(__name__, )
logger.setLevel(level=logging.INFO)


class Player(ABC):
    def __init__(self, player_number: int, suppress_logs: bool = False) -> None:
        self.socket: zmq.Socket
        self.state = PlayerState(player_number=player_number)
        if suppress_logs:
            logger.setLevel(level=logging.ERROR)

    def bind_to_socket(
        self,
    ) -> None:
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.bind("tcp://*:5000")
        logger.info("Bound to port 5000")

    def run_communication_loop(self) -> None:

        while True:
            message = self.socket.recv()
            response = self.handle_communication(message=message)
            self.socket.send_string(response)

    def handle_communication(self, message: bytes) -> str:
        message_dict = json.loads(message)
        if message_dict["type"] == "update":
            self.handle_update(message_dict=message_dict)
            response = ""
        elif message_dict["type"] == "request":
            logger.info("Request received")
            response = self.handle_request(message_dict=message_dict)
            logger.info("Sending response")

        return response

    def handle_update(self, message_dict: dict) -> None:
        update = Update.parse_raw(message_dict["update"])
        self.state.update_state(update=update)
        print_update(update=update)

    def get_available_plays(self) -> list[str]:
        available_cards = self.state.get_available_cards()
        last_play = self.state.get_last_play()
        discard_pile = self.state.get_discard_pile()
        available_plays = get_available_plays_from_stack(
            stack=available_cards, last_play=last_play, discard_pile=discard_pile
        )
        return list(available_plays)

    @abstractmethod
    def handle_request(self, message_dict: dict) -> str:
        raise NotImplementedError("Method not implemented")


def print_update(update: Update) -> None:
    print_list = [update.update_type.name]

    if update.player_number is not None:
        print_list.append(f"player number: {update.player_number}")

    if update.cards is not None:
        print_list.append(f"cards: {update.cards}")

    if update.message is not None:
        print_list.append(f"message: {update.message}")

    print_message = ", ".join(print_list)
    logger.info(print_message)
