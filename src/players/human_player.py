import logging

from src.constants import PLAY_RANKS, TABLE_STACKS
from src.game_types import Action, Response
from src.players.abstract_player import Player

logging.basicConfig(level=logging.INFO)


class HumanPlayer(Player):
    def handle_request(self, message_dict: dict) -> str:

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

        return response.json()

    def print_hand(self) -> None:
        hand_cards = self.state.get_hand_cards_list()
        table_cards = self.state.get_table_cards_list()
        hand_cards.sort(key=lambda x: PLAY_RANKS[x[1]])
        table_cards.sort(key=lambda x: PLAY_RANKS[x[1]])
        logging.info(f"Hand cards: {hand_cards}")
        logging.info(f"Table cards: {table_cards}")
