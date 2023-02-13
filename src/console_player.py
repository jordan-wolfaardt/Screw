import json
import logging
import sys
from abc import ABC, abstractmethod

import zmq

from src.constants import TABLE_STACKS
from src.game_types import Action, Response, Update, UpdateType

logging.basicConfig(level=logging.INFO)


class Player(ABC):
    def __init__(self, player_number: int) -> None:
        self.socket: zmq.Socket
        self.hand_set: set[str] = set()
        self.table_set: set[str] = set()
        self.table_stacks = TABLE_STACKS
        self.unaccepted_play_cards: str
        self.player_number = player_number

    def bind_to_socket(
        self,
    ) -> None:
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.bind("tcp://*:5000")
        logging.info("Bound to port 5000")

    def run_communication_loop(self) -> None:

        while True:
            message = self.socket.recv()
            message_dict = json.loads(message)
            if message_dict["type"] == "update":
                self.handle_update(message_dict=message_dict)
            elif message_dict["type"] == "request":
                self.handle_request(message_dict=message_dict)

    def handle_update(self, message_dict: dict) -> None:

        update = Update.parse_raw(message_dict["update"])
        self.update_hand(update=update)
        print_update(update=update)
        self.socket.send_string("")

    def update_hand(self, update: Update) -> None:
        match update.update_type:
            case UpdateType.GAME_INITIATED:
                self.hand_set = set()
                self.table_set = set()
            case UpdateType.YOU_DREW_CARD:
                assert update.cards
                self.hand_set.add(update.cards)
            case UpdateType.YOU_PICKED_UP_DISCARD_PILE:
                assert update.cards
                for card in update.cards.split(","):
                    self.hand_set.add(card)
            case _:
                pass

        if getattr(update, "player_number", -1) == self.player_number:
            match update.update_type:
                case UpdateType.PLAY_FROM_FACEDOWN_SUCCESS:
                    self.table_stacks -= 1
                case UpdateType.PLAY_FROM_FACEDOWN_FAILURE:
                    assert update.cards
                    self.hand_set.add(update.cards)
                    self.table_stacks -= 1
                case UpdateType.PLAY_FROM_FACEUP_FAILURE:
                    for card in self.unaccepted_play_cards.split(","):
                        self.hand_set.add(card)
                        self.table_set.remove(card)
                case UpdateType.SET_TABLE_CARDS:
                    card_list = self.unaccepted_play_cards.split(",")
                    for card in card_list:
                        self.table_set.add(card)
                        self.hand_set.remove(card)
                case UpdateType.PLAY_FROM_HAND:
                    card_list = self.unaccepted_play_cards.split(",")
                    for card in card_list:
                        self.hand_set.remove(card)
                case UpdateType.PLAY_FROM_TABLE:
                    card_list = self.unaccepted_play_cards.split(",")
                    for card in card_list:
                        self.table_set.remove(card)
                case _:
                    pass

    @abstractmethod
    def handle_request(self, message_dict: dict) -> None:
        raise NotImplementedError("Method not implemented")


class HumanPlayer(Player):
    def handle_request(self, message_dict: dict) -> None:

        logging.info("Request received")

        if message_dict["request_type"] == "SET_TABLE_CARDS":
            encoded_cards = input(f"Set your {TABLE_STACKS} table cards, i.e. 'HQ,ST,S9'\n")
            response = Response(action=Action.SET_TABLE_CARDS, cards=encoded_cards)
            self.unaccepted_play_cards = encoded_cards
        elif message_dict["request_type"] == "PLAY":
            logging.info("It's your turn!")
            play_option = "0"
            while play_option not in ["1", "2"]:
                play_option = input(
                    "Enter 1 to pick up discard pile, 2 to play cards, or 3 to see your hand\n"
                )
                if play_option == "3":
                    self.print_hand()
            if play_option == "1":
                response = Response(action=Action.PICK_UP_DISCARD_PILE)
            elif play_option == "2":
                encoded_cards = input("Enter the cards you want to play, i.e. 'HQ,SQ'\n")
                response = Response(action=Action.PLAY_KNOWN_CARDS, cards=encoded_cards)
                self.unaccepted_play_cards = encoded_cards

        self.socket.send_string(response.json())

        logging.info("Response sent")

    def print_hand(self) -> None:
        hand_cards = list(self.hand_set)
        table_cards = list(self.table_set)
        hand_cards.sort(key=lambda x: x[1])
        table_cards.sort(key=lambda x: x[1])
        logging.info(f"Hand cards: {hand_cards}")
        logging.info(f"Table cards: {table_cards}")


class ComputerPlayer(Player):
    def handle_request(self, message_dict: dict) -> None:
        raise NotImplementedError("ComputerPlayer is not implemented yet")


def print_update(update: Update) -> None:

    print_list = [update.update_type.name]

    if update.player_number is not None:
        print_list.append(f"player number: {update.player_number}")

    if update.cards is not None:
        print_list.append(f"cards: {update.cards}")

    if update.message is not None:
        print_list.append(f"message: {update.message}")

    print_message = ", ".join(print_list)
    logging.info(print_message)


if __name__ == "__main__":

    player_number = int(sys.argv[1])

    player = HumanPlayer(player_number=player_number)
    player.bind_to_socket()
    player.run_communication_loop()