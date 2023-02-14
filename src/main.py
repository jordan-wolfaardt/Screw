import json
import logging
import sys
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection

import zmq

from src.game import Game
from src.messaging import Messaging

context = zmq.Context()

logging.basicConfig(level=logging.INFO)


def run_game(number_of_players: int, connection: Connection) -> None:

    messaging = Messaging(number_of_players=number_of_players, connection=connection)
    game = Game(number_of_players=number_of_players, messaging=messaging)
    game.setup()
    game.run()
    connection.send("Exiting")

    return


def create_socket_connections(number_of_players: int) -> dict:
    sockets: dict[int, zmq.Socket] = {}

    for i in range(number_of_players):
        socket = context.socket(zmq.REQ)
        socket.connect(f"tcp://player{i}:5000")
        sockets[i] = socket

    return sockets


def route_communication(connection: Connection, sockets: dict) -> bool:

    message = connection.recv()
    logging.info(f"Message from game: {message}")

    if message == "Exiting":
        return False
    else:
        message_dict = json.loads(message)
        player_number = message_dict["recipient"]
        socket = sockets[player_number]
        socket.send_string(message)
        response = socket.recv()
        logging.info(f"Response: {response}")
        connection.send(response)

    return True


if __name__ == "__main__":

    number_of_players = int(sys.argv[1])

    sockets = create_socket_connections(number_of_players=number_of_players)

    conn_main, conn_game = Pipe(duplex=True)

    game_process = Process(target=run_game, args=(number_of_players, conn_game))

    logging.info("Starting game")
    game_process.start()

    while route_communication(connection=conn_main, sockets=sockets):
        pass

    game_process.join()
