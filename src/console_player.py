import json
import logging
import sys
from abc import ABC, abstractmethod
from itertools import combinations
from random import randint

import zmq

from src.constants import PLAY_RANKS, TABLE_STACKS
from src.game_types import Action, Response, Update
from src.player_state import PlayerState
from src.utilities import get_available_plays_from_stack

logging.basicConfig(level=logging.INFO)


class Player(ABC):
    def __init__(self, player_number: int) -> None:
        self.socket: zmq.Socket
        self.game_state = PlayerState(player_number=player_number)

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
        self.game_state.update_state(update=update)
        print_update(update=update)
        self.socket.send_string("")

    def get_available_plays(self) -> list[str]:
        available_cards = self.game_state.get_available_cards()
        last_play = self.game_state.get_last_play()
        discard_pile = self.game_state.get_discard_pile()
        available_plays = get_available_plays_from_stack(
            stack=available_cards, last_play=last_play, discard_pile=discard_pile
        )
        return list(available_plays)

    @abstractmethod
    def handle_request(self, message_dict: dict) -> None:
        raise NotImplementedError("Method not implemented")


class HumanPlayer(Player):
    def handle_request(self, message_dict: dict) -> None:

        logging.info("Request received")

        if message_dict["request_type"] == "SET_TABLE_CARDS":
            encoded_cards = input(f"Set your {TABLE_STACKS} table cards, i.e. 'HQ,ST,S9'\n")
            response = Response(action=Action.SET_TABLE_CARDS, cards=encoded_cards)
        elif message_dict["request_type"] == "PLAY":
            logging.info("It's your turn!")
            self.print_hand()
            play = input(
                "Enter '1' to pick up discard pile or enter the cards you want to play, i.e. 'HQ,SQ'\n"
            )
            if play == "1":
                response = Response(action=Action.PICK_UP_DISCARD_PILE)
            else:
                response = Response(action=Action.PLAY_KNOWN_CARDS, cards=play)

        self.socket.send_string(response.json())

        logging.info("Response sent")

    def print_hand(self) -> None:
        hand_cards = self.game_state.get_hand_cards_list()
        table_cards = self.game_state.get_table_cards_list()
        hand_cards.sort(key=lambda x: PLAY_RANKS[x[1]])
        table_cards.sort(key=lambda x: PLAY_RANKS[x[1]])
        logging.info(f"Hand cards: {hand_cards}")
        logging.info(f"Table cards: {table_cards}")


class ComputerPlayer(Player):
    def handle_request(self, message_dict: dict) -> None:

        logging.info("Request received")

        if message_dict["request_type"] == "SET_TABLE_CARDS":
            encoded_cards = self.set_table_cards()
            response = Response(action=Action.SET_TABLE_CARDS, cards=encoded_cards)
        elif message_dict["request_type"] == "PLAY":
            play = self.play()
            if play == "1":
                response = Response(action=Action.PICK_UP_DISCARD_PILE)
            else:
                response = Response(action=Action.PLAY_KNOWN_CARDS, cards=play)

        self.socket.send_string(response.json())

        logging.info("Response sent")

    @abstractmethod
    def set_table_cards(self) -> str:
        raise NotImplementedError("Method not implemented")

    @abstractmethod
    def play(self) -> str:
        raise NotImplementedError("Method not implemented")


class RandomPlayer(ComputerPlayer):
    def set_table_cards(self) -> str:
        hand_cards = self.game_state.get_hand_cards_list()
        card_combinations = [
            ",".join(combination) for combination in combinations(hand_cards, TABLE_STACKS)
        ]
        chosen_combination = pick_one(options=card_combinations)
        return chosen_combination

    def play(self) -> str:
        options = []
        if self.game_state.get_last_play() is not None:
            options.append("1")
        available_plays = self.get_available_plays()
        options += available_plays
        return pick_one(options=options)


class GreedyPlayer(ComputerPlayer):
    def set_table_cards(self) -> str:
        hand_cards = self.game_state.get_hand_cards_list()
        selected_table_cards = greedy_select_table_cards(card_list=hand_cards)
        return selected_table_cards

    def play(self) -> str:
        available_plays = self.get_available_plays()
        if not len(available_plays):
            return "1"

        chosen_play = greedy_select_play(available_plays=available_plays)
        return chosen_play


def pick_one(options: list[str]) -> str:
    chosen_index = randint(0, len(options) - 1)
    return options[chosen_index]


def greedy_select_table_cards(card_list: list[str]) -> str:
    card_list.sort(key=lambda c: PLAY_RANKS[c[1]], reverse=True)
    return ",".join(card_list[:3])


def greedy_select_play(available_plays: list[str]) -> str:
    available_plays.sort(key=lambda c: (PLAY_RANKS[c[1]], -len(c)))
    return available_plays[0]


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
    player_type = sys.argv[2]

    player_class: type[Player]

    if player_type == "human":
        player_class = HumanPlayer
    if player_type == "random":
        player_class = RandomPlayer
    if player_type == "greedy":
        player_class = GreedyPlayer

    player = player_class(player_number=player_number)
    player.bind_to_socket()
    player.run_communication_loop()
