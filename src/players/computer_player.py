from abc import abstractmethod

from src.game_types import Action, Response
from src.players.abstract_player import Player


class ComputerPlayer(Player):

    def handle_request(self, message_dict: dict) -> str:
        if message_dict["request_type"] == "SET_TABLE_CARDS":
            encoded_cards = self.set_table_cards()
            response = Response(action=Action.SET_TABLE_CARDS, cards=encoded_cards)
        elif message_dict["request_type"] == "PLAY":
            play = self.play()
            if play == "1":
                response = Response(action=Action.PICK_UP_DISCARD_PILE)
            else:
                response = Response(action=Action.PLAY_KNOWN_CARDS, cards=play)

        return response.json()

    @abstractmethod
    def set_table_cards(self) -> str:
        raise NotImplementedError("Method not implemented")

    @abstractmethod
    def play(self) -> str:
        raise NotImplementedError("Method not implemented")
