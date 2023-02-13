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
    does_hand_have_known_cards,
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
        self.eliminated_cards = Stack()
        self.win: Optional[int] = None

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

    def assert_conservation_of_cards(self) -> None:
        count_players_cards = sum(count_player_cards(hand) for hand in self.player_hands)
        total_cards = (
            len(self.deck)
            + len(self.discard_pile)
            + len(self.eliminated_cards)
            + count_players_cards
        )
        assert total_cards == DECK_LEN

    def loop_until_valid_table_cards(self, player_number: int) -> None:

        valid_play = False

        while not valid_play:

            valid_play = self.handle_table_card_selection(player_number=player_number)

    def handle_table_card_selection(self, player_number: int) -> bool:

        try:
            self.receive_table_card_selection(player_number=player_number)
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
        if len(self.deck):
            dealt_cards = self.deck.deal(num=1)
            card = dealt_cards.cards[0]
            self.player_hands[player_number].hand_stack += dealt_cards
            self.messaging.card_draw(player_number=player_number, card=card)
            if not len(self.deck):
                self.messaging.deck_depleted()

    def run(self) -> None:
        while self.win is None:
            self.loop_until_valid_play(player_number=self.player_turn)
            self.assert_conservation_of_cards()

    def loop_until_valid_play(self, player_number: int) -> None:

        valid_play = False

        while not valid_play:
            valid_play = self.get_valid_play(player_number=player_number)

    def get_valid_play(self, player_number: int) -> bool:

        try:
            play = self.receive_and_validate_play(player_number=player_number)
            self.update_game_state_for_play(play=play, player_number=player_number)
            return True
        except CardsNotAvailableException as e:
            logging.warning(f"get_valid_play error: {e}")
            message = "Cards not available for play, try again"
        except Exception as e:
            logging.warning(f"get_valid_play error: {e}")
            traceback.print_exc()
            message = "Illegal play, try again"

        self.messaging.invalid_action(player_number=player_number, message=message)
        return False

    def receive_and_validate_play(self, player_number: int) -> Play:

        play: Play

        if does_hand_have_known_cards(hand=self.player_hands[player_number]):
            response = self.handle_request(
                player_number=player_number, request_type=RequestType.PLAY
            )
            play = convert_response_to_play(response=response)
            self.validate_play(play=play, player_number=player_number)
        else:
            play = Play(action=Action.PLAY_FACE_DOWN)
        return play

    def handle_request(self, player_number: int, request_type: RequestType) -> Response:
        response = self.messaging.request(player_number=player_number, request_type=request_type)
        return response

    def validate_play(self, play: Play, player_number: int) -> None:

        assert play.action in [Action.PICK_UP_DISCARD_PILE, Action.PLAY_KNOWN_CARDS]

        if play.action == Action.PICK_UP_DISCARD_PILE:
            assert len(self.discard_pile) > 0
        else:
            assert play.cards
            assert len(play.cards)
            assert are_all_cards_same_value(play.cards)
            if len(self.player_hands[player_number].hand_stack):
                assert is_play_available(
                    hand=self.player_hands[player_number],
                    last_play=self.last_play,
                    cards_played=play.cards,
                    discard_pile=self.discard_pile,
                )

    def update_game_state_for_play(self, play: Play, player_number: int) -> None:
        if play.action == Action.PICK_UP_DISCARD_PILE:
            self.pickup_discard_pile(player_number=player_number)
        elif play.action == Action.PLAY_FACE_DOWN:
            self.handle_face_down_play(player_number=player_number)
        else:
            if len(self.player_hands[player_number].hand_stack):
                self.handle_play_from_hand(player_number=player_number, cards_played=play.cards)
            else:
                self.handle_face_up_play(player_number=player_number, cards_played=play.cards)

    def handle_face_down_play(self, player_number: int) -> None:
        table_stack = self.player_hands[player_number].table_stacks.pop()
        card = table_stack.bottom_card
        card_stack = Stack(cards=[card])

        if does_play_trump_last_play(cards_played=card_stack, last_play=self.last_play):
            self.play_cards(player_number=player_number, cards=card_stack)
            self.messaging.play_from_facedown_success(player_number=player_number, card=card)
        else:
            self.player_hands[player_number].hand_stack += card_stack
            self.pickup_discard_pile(player_number=player_number)
            self.messaging.play_from_facedown_failure(player_number=player_number, card=card)

    def handle_face_up_play(self, player_number: int, cards_played: Stack) -> None:
        if is_play_available(
            hand=self.player_hands[player_number],
            last_play=self.last_play,
            cards_played=cards_played,
            discard_pile=self.discard_pile,
        ):
            self.remove_cards_from_face_up(player_number=player_number, cards=cards_played)
            self.play_cards(player_number=player_number, cards=cards_played)
            self.messaging.play_from_table(player_number=player_number, cards=cards_played)
        else:
            try:
                self.remove_cards_from_face_up(player_number=player_number, cards=cards_played)
                self.player_hands[player_number].hand_stack += cards_played
                self.messaging.play_from_faceup_failure(
                    player_number=player_number, cards=cards_played
                )
            except CardsNotAvailableException:
                pass
            self.pickup_discard_pile(player_number=player_number)

    def handle_play_from_hand(self, player_number: int, cards_played: Stack) -> None:
        self.remove_cards_from_hand_stack(player_number=player_number, cards=cards_played)
        self.play_cards(player_number=player_number, cards=cards_played)
        self.messaging.play_from_hand(player_number=player_number, cards=cards_played)

    def pickup_discard_pile(self, player_number: int) -> None:
        cards_list = self.discard_pile.empty(return_cards=True)
        cards = Stack(cards=cards_list)
        self.player_hands[player_number].hand_stack += cards
        self.last_play = None
        self.update_turn(count=1)
        self.messaging.discard_pile_pickup(player_number=player_number, cards=cards)

    def play_cards(self, player_number: int, cards: Stack) -> None:
        stored_last_play = self.last_play
        self.last_play = cards
        self.discard_pile += cards

        if self.check_victory(player_number=player_number):
            self.win = player_number

        if self.check_for_burn():
            cards_list = self.discard_pile.empty(return_cards=True)
            self.last_play = None
            self.eliminated_cards += Stack(cards=cards_list)
            self.messaging.burn_discard_pile()
        else:
            self.deal_card(player_number=player_number)
            if (
                stored_last_play
                and stored_last_play.cards[0].value == self.last_play[0].value
                and self.last_play[0].value != "2"
            ):
                self.update_turn(count=2)
            else:
                self.update_turn(count=1)

    def update_turn(self, count: int) -> None:
        self.player_turn = (self.player_turn + count) % self.number_of_players

    def check_for_burn(self) -> bool:
        assert self.last_play is not None
        if self.last_play[0].value == "10":
            return True
        if (
            len(self.discard_pile) >= 4
            and self.last_play[0].value != "2"
            and are_all_cards_same_value(stack=self.discard_pile[-4:])
        ):
            return True
        return False

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

        count_cards_to_remove = len(cards)
        count_cards_removed = 0

        for card in cards:
            found = False
            for table_stack in self.player_hands[player_number].table_stacks:
                if table_stack.top_card == card:
                    table_stack.top_card = None
                    found = True
                    break
            if found:
                count_cards_removed += 1

        if count_cards_removed != count_cards_to_remove:
            raise CardsNotAvailableException("Cards not found on table")

    def check_victory(self, player_number: int) -> bool:
        victory = (not len(self.player_hands[player_number].table_stacks)) and (
            not len(self.player_hands[player_number].hand_stack)
        )
        if victory:
            self.messaging.player_wins(player_number=self.player_turn)
        return victory
