import json

import zmq

from src.constants import TABLE_STACKS
from src.game_types import Action, Response, Update


def communication_loop(socket: zmq.sugar.context.ST) -> None:

    while True:
        message = socket.recv()
        message_dict = json.loads(message)
        if message_dict["type"] == "update":
            handle_update(message_dict=message_dict, socket=socket)
        elif message_dict["type"] == "request":
            handle_request(message_dict=message_dict, socket=socket)


def handle_update(message_dict: dict, socket: zmq.sugar.context.ST) -> None:

    print("Update received")

    for update_string in message_dict["payload"]:
        create_and_print_update_message(update_string=update_string)
    socket.send_string("")

    print("Update complete\n")


def create_and_print_update_message(update_string: str) -> None:
    update = Update.parse_raw(update_string)

    print_list = [update.update_type.name]

    if update.player_number is not None:
        print_list.append(f"player number: {update.player_number}")

    if update.cards is not None:
        print_list.append(f"cards: {update.cards}")

    if update.message is not None:
        print_list.append(f"message: {update.message}")

    print_message = ", ".join(print_list)
    print(print_message)


def handle_request(message_dict: dict, socket: zmq.sugar.context.ST) -> None:

    print("Request received")

    if message_dict["request_type"] == "SET_TABLE_CARDS":
        encoded_cards = input(f"Set your {TABLE_STACKS} table cards, i.e. 'HQ,ST,S9'\n")
        response = Response(action=Action.SET_TABLE_CARDS, cards=encoded_cards)
    elif message_dict["request_type"] == "PLAY":
        print("It's your turn!")
        play_option = 0
        while play_option not in ["1", "2"]:
            play_option = input("Enter 1 to pick up discard pile or 2 to play cards\n")
        if play_option == "1":
            response = Response(action=Action.PICK_UP_DISCARD_PILE)
        else:
            encoded_cards = input("Enter the cards you want to play, i.e. 'HQ,SQ'\n")
            response = Response(action=Action.PLAY_KNOWN_CARDS, cards=encoded_cards)

    socket.send_string(response.json())

    print("Response sent\n")


def bind_to_socket() -> zmq.sugar.context.ST:

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:5000")
    print("Bound to port 5000")

    return socket


if __name__ == "__main__":

    socket = bind_to_socket()
    communication_loop(socket=socket)
