import sys

from src.players.abstract_player import Player
from src.players.greedy_player import GreedyPlayer
from src.players.human_player import HumanPlayer
from src.players.random_player import RandomPlayer
from src.players.simple_mcts_player import SimpleMCTS


if __name__ == "__main__":

    player_number = int(sys.argv[1])
    player_type = sys.argv[2]

    player_class: type[Player]

    if player_type == "human":
        player_class = HumanPlayer
    elif player_type == "random":
        player_class = RandomPlayer
    elif player_type == "greedy":
        player_class = GreedyPlayer
    elif player_type == "simpleMCTS":
        player_class = SimpleMCTS
    else:
        raise Exception(f"player_type invalid {player_type}")

    player = player_class(player_number=player_number)
    player.bind_to_socket()
    player.run_communication_loop()
