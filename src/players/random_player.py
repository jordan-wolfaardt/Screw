from itertools import combinations
from random import randint

from src.constants import TABLE_STACKS
from src.players.computer_player import ComputerPlayer


class RandomPlayer(ComputerPlayer):
    def set_table_cards(self) -> str:
        hand_cards = self.state.get_hand_cards_list()
        card_combinations = [
            ",".join(combination) for combination in combinations(hand_cards, TABLE_STACKS)
        ]
        chosen_combination = pick_one(options=card_combinations)
        return chosen_combination

    def play(self) -> str:
        options = []
        if self.state.get_last_play() is not None:
            options.append("1")
        available_plays = self.get_available_plays()
        options += available_plays
        return pick_one(options=options)


def pick_one(options: list[str]) -> str:
    chosen_index = randint(0, len(options) - 1)
    return options[chosen_index]
