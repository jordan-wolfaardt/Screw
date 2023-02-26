import json
import logging
from itertools import combinations
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection

from src.constants import TABLE_STACKS
from src.game_types import Action, Response
from src.player_state import build_game, build_player_states, GameState, PlayerState
from src.players.computer_player import ComputerPlayer
from src.players.greedy_player import GreedyPlayer

logging.basicConfig(level=logging.INFO)


class SimpleMCTS(ComputerPlayer):
    # One Layer Uniform Distribution Monte Carlo Tree Search

    def set_table_cards(self) -> str:
        hand_cards = self.state.get_hand_cards_list()
        card_combinations = [
            ",".join(combination) for combination in combinations(hand_cards, TABLE_STACKS)
        ]

        if self.state.deck_length < 10:
            iterations = 30
        else:
            iterations = 5

        chosen_cards = uniform_monte_carlo_tree_search(
            player_state=self.state, iterations=iterations, play_options=card_combinations
        )
        return chosen_cards

    def play(self) -> str:
        options = []
        if self.state.get_last_play() is not None:
            options.append("1")
        available_plays = self.get_available_plays()
        options += available_plays

        if self.state.deck_length < 10:
            iterations = 30
        else:
            iterations = 5

        chosen_play = uniform_monte_carlo_tree_search(
            player_state=self.state, iterations=iterations, play_options=options
        )
        return chosen_play


def uniform_monte_carlo_tree_search(
    player_state: PlayerState, iterations: int, play_options: list[str]
) -> str:

    win_pct: float = 0
    chosen_play = play_options[0]
    logging.info(f"test plays {play_options} with {iterations} iterations")

    if len(play_options) > 1:
        for play in play_options:
            play_win_pct = test_play(
                player_state=player_state,
                iterations=iterations,
                play=play,
            )
            logging.info(f"play {play} wins {round(play_win_pct, 3)}")
            if play_win_pct > win_pct:
                win_pct = play_win_pct
                chosen_play = play

    logging.info(f"choosing play {chosen_play}")
    return chosen_play


def test_play(
    player_state: PlayerState,
    iterations: int,
    play: str,
) -> float:
    wins = 0
    for i in range(iterations):
        if simulate(
            player_state=player_state,
            play=play,
        ):
            wins += 1
    return wins / iterations


def simulate(
    player_state: PlayerState,
    play: str,
) -> bool:

    player_number = player_state.player_number

    game_state = player_state.create_game_state()
    connection_main, connection_game = Pipe(duplex=True)
    players = create_players(game_state=game_state, player_class=GreedyPlayer)

    game_process = Process(target=simulate_game, args=(game_state, connection_game, player_state.player_number))
    game_process.start()

    # play chosen play
    while True:
        message = connection_main.recv()
        message_dict = json.loads(message)
        if message_dict["type"] == "update":
            connection_main.send("")
        elif message_dict["type"] == "request":
            assert message_dict["recipient"] == player_number
            if message_dict["request_type"] == "SET_TABLE_CARDS":
                response = Response(action=Action.SET_TABLE_CARDS, cards=play)
            elif play == "1":
                response = Response(action=Action.PICK_UP_DISCARD_PILE)
            else:
                response = Response(action=Action.PLAY_KNOWN_CARDS, cards=play)
            connection_main.send(response.json())
            break
        else:
            raise Exception(f"message type invalid {message_dict}")

    # simulate rest of game
    i = 0
    while route_communication(connection=connection_main, players=players, play=play):
        i += 1
        if i > 600:
            # game simulation probably stuck in loop. Break
            game_process.terminate()
            logging.debug("Breaking iteration")
            break

    game_process.join()

    return players[player_number].state.win == player_number


def create_players(
    game_state: GameState, player_class: type[ComputerPlayer]
) -> list[ComputerPlayer]:
    player_states = build_player_states(game_state=game_state)
    players = [player_class(player_number=i, suppress_logs=True) for i in range(game_state.number_of_players)]
    for i in range(game_state.number_of_players):
        players[i].state = player_states[i]
    return players


def simulate_game(
    game_state: GameState,
    connection_game: Connection,
    player_number: int,
) -> None:

    game = build_game(game_state=game_state, connection=connection_game)

    if game.table_cards_set is False:
        game.set_table_cards(start_player_number=player_number)
    game.run()
    connection_game.send("Exiting")


def route_communication(connection: Connection, players: list[ComputerPlayer], play: str) -> bool:

    message = connection.recv()
    logging.debug(f"Message from game: {message}")

    if message == "Exiting":
        return False
    else:
        message_dict = json.loads(message)
        player_number = message_dict["recipient"]
        response = players[player_number].handle_communication(message=message)
        logging.debug(f"Response: {response}")
        connection.send(response)

    return True
