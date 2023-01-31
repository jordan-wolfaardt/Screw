import logging
import traceback
from typing import Optional

from pydealer import (  # type: ignore
    Deck,
    Stack,
)

from src.constants import (
    DECK_LEN,
    HAND_CARDS,
    MAX_PLAYERS,
    MIN_PLAYERS,
    TABLE_STACKS,
)
from src.exceptions import CardEncodeDecodeException, CardsNotAvailableException
from src.game_types import Action, Hand, Play, RequestType, Response, TableStack
from src.messaging import Messaging
from src.utilities import (
    are_all_cards_same_value,
    build_face_up_table_stack,
    card_set_from_stack,
    convert_response_to_play,
    count_player_cards,
    deserialize_cards,
    do_face_up_table_cards_exist,
    does_play_trump_last_play,
    is_play_available,
)


class Game:
    def __init__(self, number_of_players: int, messaging: Messaging) -> None:
        assert MIN_PLAYERS <= number_of_players <= MAX_PLAYERS
        self.number_of_players = number_of_players
        self.discard_pile = Stack()
        self.last_play: Optional[Stack] = None
        self.player_turn = 0

        self.deck = Deck()

        self.player_hands: list[Hand] = [Hand() for i in range(number_of_players)]

        self.messaging = messaging

        self.messaging.game_initiated()

        self.assert_conservation_of_cards()

    def setup(self) -> None:

        self.deck.shuffle()

        self.initial_deal()

        self.set_table_cards()

        self.assert_conservation_of_cards()

    def initial_deal(self) -> None:

        self.deal_table_cards()

        self.deal_hand_cards()

    def set_table_cards(self) -> None:

        for player_number in range(self.number_of_players):
            self.loop_until_valid_table_cards(player_number=player_number)

    def loop_until_valid_table_cards(self, player_number: int) -> None:

        valid_play = False

        while not valid_play:

            valid_play = self.handle_table_card_selection(player_number=player_number)

    def handle_table_card_selection(self, player_number: int) -> bool:

        try:
            self.receive_table_card_selection(player_number=player_number)
            self.messaging.play_accepted(player_number=player_number)
            return True
        except AssertionError as e:
            logging.warning(f"handle_table_card_selection error: {e}")
            message = "Card selection not valid, cards must be {TABLE_STACKS} unique cards"
        except CardsNotAvailableException as e:
            logging.warning(f"handle_table_card_selection error: {e}")
            message = "Those cards are not in hand to be placed, try again"
        except CardEncodeDecodeException as e:
            logging.warning(f"handle_table_card_selection error: {e}")
            message = "Error parsing cards, try again"
        except Exception as e:
            traceback.print_exc()
            logging.warning(f"handle_table_card_selection error: {e}")
            message = "Server error, try again"

        self.messaging.invalid_action(player_number=player_number, message=message)

        return False

    def receive_table_card_selection(self, player_number: int) -> None:

        response = self.handle_request(
            player_number=player_number, request_type=RequestType.SET_TABLE_CARDS
        )

        assert response.action == Action.SET_TABLE_CARDS
        assert response.cards

        cards = deserialize_cards(encoded_cards=response.cards)

        assert len({card.abbrev for card in cards}) == len(cards)
        assert len(cards) == TABLE_STACKS

        self.remove_cards_from_hand_stack(player_number=player_number, cards=cards)
        self.messaging.set_table_cards(player_number=player_number, cards=cards)

        self.place_table_cards(player_number=player_number, stack=cards)

    def place_table_cards(self, player_number: int, stack: Stack) -> None:
        for i, card in enumerate(stack):
            self.player_hands[player_number].table_stacks[i].top_card = card

    def deal_table_cards(self) -> None:
        for i in range(TABLE_STACKS):
            for player_number in range(self.number_of_players):
                self.deal_table_card(player_number=player_number)

    def deal_table_card(self, player_number: int) -> None:
        card_list = self.deck.deal(num=1)
        table_stack = TableStack(
            top_card=None,
            bottom_card=card_list[0],
        )
        self.player_hands[player_number].table_stacks.append(table_stack)

    def deal_hand_cards(self) -> None:

        for i in range(HAND_CARDS + TABLE_STACKS):
            for player_number in range(self.number_of_players):
                self.deal_card(player_number=player_number)

    def deal_card(self, player_number: int) -> None:
        dealt_cards = self.deck.deal(num=1)
        card = dealt_cards.cards[0]
        self.player_hands[player_number].hand_stack += dealt_cards
        self.messaging.card_draw(player_number=player_number, card=card)
        if not len(self.deck):
            self.messaging.deck_depleted()

    def run(self) -> None:

        player_wins = False

        while not player_wins:

            stored_last_play = self.last_play

            self.handle_play(player_number=self.player_turn)

            player_wins = self.check_victory(player_number=self.player_turn)

            if player_wins:
                self.messaging.player_wins(player_number=self.player_turn)

            self.handle_turn_update(stored_last_play=stored_last_play)

            self.assert_conservation_of_cards()

    def handle_turn_update(self, stored_last_play: Optional[Stack]) -> None:

        if self.last_play is None:
            # self.last_play is None means the player picked up the discard pile
            update = 1
        elif self.last_play[0].value == "10":
            # playing 10 means players gets to go again
            update = 0
        elif self.last_play[0].value == "2" or stored_last_play is None:
            # playing 2 again does not skip the next player
            # if previous play (stored_last_play) is None then play cannot be repeated
            update = 1
        elif stored_last_play.cards[0].value == self.last_play[0].value:
            # repating the same card values means the next player gets skipped
            update = 2
        else:
            # non-repeating cards are played, so turn progresses as usual
            update = 1

        self.player_turn = (self.player_turn + update) % self.number_of_players

    def handle_play(self, player_number: int) -> None:
        play = self.loop_until_valid_play(player_number=player_number)
        self.update_game_state_for_play(play=play, player_number=player_number)

    def loop_until_valid_play(self, player_number: int) -> Play:

        valid_play = False

        while not valid_play:

            play = self.get_valid_play(player_number=player_number)
            if play is not None:
                valid_play = True

        assert play
        return play

    def get_valid_play(self, player_number: int) -> Optional[Play]:

        try:
            play = self.receive_and_validate_play(player_number=player_number)
            self.messaging.play_accepted(player_number=player_number)
            return play
        except CardsNotAvailableException as e:
            logging.warning(f"get_valid_play error: {e}")
            message = "Cards not available for play, try again"
        except Exception as e:
            logging.warning(f"get_valid_play error: {e}")
            traceback.print_exc()
            message = "Illegal play, try again"

        self.messaging.invalid_action(player_number=player_number, message=message)
        return None

    def receive_and_validate_play(self, player_number: int) -> Play:

        play: Play

        if not (
            len(self.player_hands[player_number].hand_stack)
            or len(
                build_face_up_table_stack(
                    table_stacks=self.player_hands[player_number].table_stacks
                )
            )
        ):
            play = self.handle_face_down_card_play(player_number=player_number)
        else:
            response = self.handle_request(
                player_number=player_number, request_type=RequestType.PLAY
            )
            play = convert_response_to_play(response=response)
            self.validate_play(play=play, player_number=player_number)

        return play

    def handle_request(self, player_number: int, request_type: RequestType) -> Response:
        response = self.messaging.update_and_request(
            player_number=player_number, request_type=request_type
        )
        return response

    def validate_play(self, play: Play, player_number: int) -> None:

        assert play.action in [Action.PLAY_KNOWN_CARDS, Action.PICK_UP_DISCARD_PILE]

        if play.action == Action.PICK_UP_DISCARD_PILE:
            assert len(self.discard_pile) > 0
        else:
            assert play.cards
            assert len(play.cards)
            assert are_all_cards_same_value(play.cards)
            assert is_play_available(
                hand=self.player_hands[player_number],
                last_play=self.last_play,
                played_cards=play.cards,
            )

    def handle_face_down_card_play(self, player_number: int) -> Play:

        table_stack = self.player_hands[player_number].table_stacks.pop()

        card = table_stack.bottom_card

        card_stack = Stack(cards=[card])

        if does_play_trump_last_play(cards_played=card_stack, last_play=self.last_play):
            play = Play(
                action=Action.PLAY_FACE_DOWN,
                cards=card_stack,
            )
            self.messaging.play_from_facedown_success(player_number=player_number, card=card)
            return play

        else:
            self.player_hands[player_number].hand_stack += card_stack
            self.messaging.play_from_facedown_failure(player_number=player_number, card=card)

            play = Play(
                action=Action.PICK_UP_DISCARD_PILE,
            )
            return play

    def update_game_state_for_play(self, play: Play, player_number: int) -> None:
        if play.action == Action.PICK_UP_DISCARD_PILE:
            cards_list = self.discard_pile.empty(return_cards=True)
            cards = Stack(cards=cards_list)
            self.player_hands[player_number].hand_stack += cards
            self.last_play = None
            self.messaging.discard_pile_pickup(player_number=player_number, cards=cards)
        elif play.action == Action.PLAY_FACE_DOWN:
            self.last_play = play.cards
        elif play.action == Action.PLAY_KNOWN_CARDS:
            self.remove_cards_from_players_hand(
                player_number=player_number, cards_played=play.cards
            )
            self.last_play = play.cards
            self.discard_pile += play.cards
            if len(self.deck):
                self.deal_card(player_number=player_number)
        else:
            raise Exception(f"Invalid play type, {play}")

    def remove_cards_from_players_hand(self, player_number: int, cards_played: Stack) -> None:

        if len(self.player_hands[player_number].hand_stack):
            self.remove_cards_from_hand_stack(player_number=player_number, cards=cards_played)
            self.messaging.play_from_hand(player_number=player_number, cards=cards_played)

        elif do_face_up_table_cards_exist(self.player_hands[player_number].table_stacks):
            self.remove_cards_from_face_up(player_number=player_number, cards=cards_played)
            self.messaging.play_from_table(player_number=player_number, cards=cards_played)

        else:
            raise CardsNotAvailableException(f"Cards not available, {cards_played}")

    def remove_cards_from_hand_stack(self, player_number: int, cards: Stack) -> None:

        hand_stack = self.player_hands[player_number].hand_stack

        if len(card_set_from_stack(cards) - card_set_from_stack(hand_stack)):
            raise CardsNotAvailableException("Cards not available to be played from hand")

        for card in cards:
            hand_stack.get(card.name)

    def remove_cards_from_face_up(self, player_number: int, cards: Stack) -> None:

        face_up_cards = build_face_up_table_stack(
            table_stacks=self.player_hands[player_number].table_stacks
        )

        if len(card_set_from_stack(cards) - card_set_from_stack(face_up_cards)):
            raise CardsNotAvailableException("Cards not available to be played from table")

        for card in cards:
            found = False
            for table_stack in self.player_hands[player_number].table_stacks:
                if table_stack.top_card == card:
                    table_stack.top_card = None
                    found = True
                    break
            if found:
                break

            raise CardsNotAvailableException("Cards not found on table")

    def check_victory(self, player_number: int) -> bool:
        return (not len(self.player_hands[player_number].table_stacks)) and (
            not len(self.player_hands[player_number].hand_stack)
        )

    def assert_conservation_of_cards(self) -> None:
        count_players_cards = sum(count_player_cards(hand) for hand in self.player_hands)
        total_cards = len(self.deck) + len(self.discard_pile) + count_players_cards
        assert total_cards == DECK_LEN
