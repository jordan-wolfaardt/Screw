from src.constants import PLAY_RANKS
from src.players.computer_player import ComputerPlayer


class GreedyPlayer(ComputerPlayer):
    def set_table_cards(self) -> str:
        hand_cards = self.state.get_hand_cards_list()
        selected_table_cards = greedy_select_table_cards(card_list=hand_cards)
        return selected_table_cards

    def play(self) -> str:
        available_plays = self.get_available_plays()
        if not len(available_plays):
            return "1"

        chosen_play = greedy_select_play(available_plays=available_plays)
        return chosen_play


def greedy_select_table_cards(card_list: list[str]) -> str:
    card_list.sort(key=lambda c: PLAY_RANKS[c[1]], reverse=True)
    return ",".join(card_list[:3])


def greedy_select_play(available_plays: list[str]) -> str:
    available_plays.sort(key=lambda c: (PLAY_RANKS[c[1]], -len(c)))
    return available_plays[0]
