from copy import deepcopy
from dataclasses import dataclass
from multiprocessing.connection import Connection
from typing import Optional

from pydealer import Card, Deck, Stack  # type: ignore

from src.constants import DECK_LEN, TABLE_STACKS
from src.game import Game
from src.game_types import Hand, TableStack, Update, UpdateType
from src.messaging import Messaging
from src.utilities import build_face_up_table_stack, deserialize_cards, is_card_in_stack, serialize_cards


@dataclass
class Opponent:
    hand_stack: Stack = Stack()
    hand_count_unknown: int = 0
    table_stack: Stack = Stack()
    table_stacks: int = TABLE_STACKS


@dataclass
class PlayerHand:
    hand_stack: Stack = Stack()
    table_stack: Stack = Stack()
    table_stacks: int = TABLE_STACKS


@dataclass
class GameState:
    deck: Deck
    discard_pile: Stack
    eliminated_cards: Stack
    player_hands: list[Hand]
    last_play: Optional[Stack]
    number_of_players: int
    player_turn: int
    win: Optional[int]
    table_cards_set: bool


class PlayerState:
    def __init__(self, player_number: int) -> None:

        self.player_number = player_number

        self.hand: PlayerHand
        self.opponents: dict[int, Opponent]
        self.last_play: Optional[Stack]
        self.discard_pile: Stack
        self.win: Optional[int]

        self.update_state_functions = {
            UpdateType.GAME_INITIATED: self.build_state,
            UpdateType.DECK_DEPLETED: self.assert_deck_empty,
            UpdateType.PLAYER_WINS: self.set_player_wins,
            UpdateType.YOU_DREW_CARD: self.you_drew_card,
            UpdateType.PLAYER_DREW_CARD: self.player_drew_card,
            UpdateType.YOU_PICKED_UP_DISCARD_PILE: self.you_picked_up_discard_pile,
            UpdateType.PLAYER_PICKED_UP_DISCARD_PILE: self.opponent_picked_up_discard_pile,
            UpdateType.BURN_DISCARD_PILE: self.burn_discard_pile,
            UpdateType.PLAY_FROM_HAND: self.play_from_hand,
            UpdateType.PLAY_FROM_TABLE: self.play_from_table,
            UpdateType.PLAY_FROM_FACEDOWN_SUCCESS: self.play_from_facedown_success,
            UpdateType.PLAY_FROM_FACEDOWN_FAILURE: self.play_from_facedown_failure,
            UpdateType.PLAY_FROM_FACEUP_FAILURE: self.play_from_faceup_failure,
            UpdateType.SET_TABLE_CARDS: self.set_table_cards,
        }

    def update_state(self, update: Update) -> None:

        player_number: Optional[int] = getattr(update, "player_number", None)
        number_of_players: Optional[int] = getattr(update, "number_of_players", None)
        if getattr(update, "cards", None) is not None:
            assert update.cards is not None
            cards = deserialize_cards(encoded_cards=update.cards)

        if update.update_type == UpdateType.GAME_INITIATED:
            assert number_of_players is not None
            self.build_state(number_of_players=number_of_players)
        elif update.update_type == UpdateType.DECK_DEPLETED:
            self.assert_deck_empty()
        elif update.update_type == UpdateType.PLAYER_WINS:
            assert player_number is not None
            self.set_player_wins(player_number=player_number)
        elif update.update_type == UpdateType.YOU_DREW_CARD:
            assert cards is not None
            self.you_drew_card(cards=cards)
        elif update.update_type == UpdateType.PLAYER_DREW_CARD:
            assert player_number is not None
            self.player_drew_card(player_number=player_number)
        elif update.update_type == UpdateType.YOU_PICKED_UP_DISCARD_PILE:
            assert cards is not None
            self.you_picked_up_discard_pile(cards=cards)
        elif update.update_type == UpdateType.PLAYER_PICKED_UP_DISCARD_PILE:
            assert player_number is not None
            self.opponent_picked_up_discard_pile(player_number=player_number)
        elif update.update_type == UpdateType.BURN_DISCARD_PILE:
            self.burn_discard_pile()
        elif update.update_type == UpdateType.PLAY_FROM_HAND:
            assert player_number is not None
            assert cards is not None
            self.play_from_hand(player_number=player_number, cards=cards)
        elif update.update_type == UpdateType.PLAY_FROM_TABLE:
            assert player_number is not None
            assert cards is not None
            self.play_from_table(player_number=player_number, cards=cards)
        elif update.update_type == UpdateType.PLAY_FROM_FACEDOWN_SUCCESS:
            assert player_number is not None
            assert cards is not None
            self.play_from_facedown_success(player_number=player_number, cards=cards)
        elif update.update_type == UpdateType.PLAY_FROM_FACEDOWN_FAILURE:
            assert player_number is not None
            assert cards is not None
            self.play_from_facedown_failure(player_number=player_number, cards=cards)
        elif update.update_type == UpdateType.PLAY_FROM_FACEUP_FAILURE:
            assert player_number is not None
            assert cards is not None
            self.play_from_faceup_failure(player_number=player_number, cards=cards)
        elif update.update_type == UpdateType.SET_TABLE_CARDS:
            assert player_number is not None
            assert cards is not None
            self.set_table_cards(player_number=player_number, cards=cards)

        self.assert_conservation_of_cards()

    def assert_conservation_of_cards(self) -> int:
        common_cards = self.deck_length + len(self.discard_pile) + len(self.eliminated_cards)
        player_cards = (
            len(self.hand.hand_stack) + len(self.hand.table_stack) + self.hand.table_stacks
        )
        opponent_cards = 0
        for opponent in self.opponents.values():
            opponent_cards += (
                len(opponent.hand_stack)
                + len(opponent.table_stack)
                + opponent.table_stacks
                + opponent.hand_count_unknown
            )

        assert common_cards + player_cards + opponent_cards == DECK_LEN

    def build_state(self, number_of_players: int) -> None:
        self.number_of_players = number_of_players
        self.deck_length = DECK_LEN - (TABLE_STACKS * number_of_players)
        self.last_play = None
        self.discard_pile = Stack()
        self.eliminated_cards = Stack()
        self.win = None
        self.table_cards_set = False

        self.opponents = dict()
        for i in range(number_of_players):
            if i != self.player_number:
                self.opponents[i] = Opponent()

        self.hand = PlayerHand()

    def assert_deck_empty(self) -> None:
        assert self.deck_length == 0

    def set_player_wins(self, player_number: int) -> None:
        if player_number == self.player_number:
            self.win = 1
        else:
            self.win = 0

    def you_drew_card(self, cards: Stack) -> None:
        self.deck_length -= 1
        self.add_cards_to_hand(cards=cards)

    def player_drew_card(self, player_number: int) -> None:
        self.deck_length -= 1
        self.opponents[player_number].hand_count_unknown += 1

    def you_picked_up_discard_pile(self, cards: Stack) -> None:
        self.add_cards_to_hand(cards=cards)
        self.discard_pile.empty()
        self.last_play = None

    def opponent_picked_up_discard_pile(self, player_number: int) -> None:
        cards_list = self.discard_pile.empty(return_cards=True)
        cards = Stack(cards=cards_list)
        self.opponents[player_number].hand_stack += cards
        self.last_play = None

    def burn_discard_pile(self) -> None:
        cards_list = self.discard_pile.empty(return_cards=True)
        cards = Stack(cards=cards_list)
        self.eliminated_cards += cards
        self.last_play = None

    def play_from_hand(self, player_number: int, cards: Stack) -> None:
        self.last_play = cards
        self.discard_pile += cards

        if player_number == self.player_number:
            self.remove_cards_from_hand(cards=cards)
        else:
            self.remove_cards_from_opponent(player_number=player_number, cards=cards)

    def add_cards_to_hand(self, cards: Stack) -> None:
        self.hand.hand_stack += cards

    def remove_cards_from_hand(self, cards: Stack) -> None:
        for card in cards:
            self.hand.hand_stack.get(card.name)

    def remove_cards_from_opponent(self, player_number: int, cards: Stack) -> None:
        number_of_cards_to_remove = len(cards)
        for card in cards:
            # if card in self.opponents[player_number].hand_stack:
            if is_card_in_stack(card=card, stack=self.opponents[player_number].hand_stack):
                self.opponents[player_number].hand_stack.get(card.name)
                number_of_cards_to_remove -= 1
        self.opponents[player_number].hand_count_unknown -= number_of_cards_to_remove

    def play_from_table(self, player_number: int, cards: Stack) -> None:
        self.last_play = cards
        self.discard_pile += cards

        if player_number == self.player_number:
            self.remove_cards_from_table(cards=cards)
        else:
            self.remove_cards_from_opponent_table(player_number=player_number, cards=cards)

    def remove_cards_from_table(self, cards: Stack) -> None:
        for card in cards:
            self.hand.table_stack.get(card.name)

    def remove_cards_from_opponent_table(self, player_number: int, cards: Stack) -> None:
        for card in cards:
            self.opponents[player_number].table_stack.get(card.name)

    def play_from_facedown_success(self, player_number: int, cards: Stack) -> None:
        self.last_play = cards
        self.discard_pile += cards

        if player_number == self.player_number:
            self.hand.table_stacks -= 1
        else:
            self.opponents[player_number].table_stacks -= 1

    def play_from_facedown_failure(self, player_number: int, cards: Stack) -> None:

        if player_number == self.player_number:
            self.hand.hand_stack += cards
            self.hand.table_stacks -= 1
        else:
            self.opponents[player_number].hand_stack += cards
            self.opponents[player_number].table_stacks -= 1

    def play_from_faceup_failure(self, player_number: int, cards: Stack) -> None:

        if player_number == self.player_number:
            self.hand.hand_stack += cards
            self.remove_cards_from_table(cards=cards)
        else:
            self.opponents[player_number].hand_stack += cards
            self.remove_cards_from_opponent_table(player_number=player_number, cards=cards)

    def set_table_cards(self, player_number: int, cards: Stack) -> None:

        if player_number == self.player_number:
            self.hand.table_stack += cards
            self.remove_cards_from_hand(cards=cards)
            self.table_cards_set = True
        else:
            self.opponents[player_number].table_stack += cards
            self.opponents[player_number].hand_count_unknown -= len(cards)

    def get_available_cards(self) -> Stack:
        if len(self.hand.hand_stack) > 0:
            return self.hand.hand_stack
        else:
            return self.hand.table_stack

    def get_hand_cards_list(self) -> list[str]:
        serialized_hand_cards = serialize_cards(cards=self.hand.hand_stack)
        return serialized_hand_cards.split(",")

    def get_table_cards_list(self) -> list[str]:
        serialized_table_cards = serialize_cards(cards=self.hand.table_stack)
        return serialized_table_cards.split(",")

    def get_last_play(self) -> Optional[Stack]:
        return self.last_play

    def get_discard_pile(self) -> Stack:
        return self.discard_pile

    def create_game_state(self) -> GameState:
        """
        This function instantiates a GameState object from the information a player knows.
        All unknown cards are assigned randomnly.
        The purpose is then the player can use the game object for simulation.
        """

        deck = Deck()
        deck.shuffle()

        table_stacks: list[TableStack]

        # set known cards
        # known cards have to be set before unknown cards so we know what to remove from the deck
        discard_pile = deepcopy(self.discard_pile)
        for card in self.discard_pile:
            deck.get(card.name)

        eliminated_cards = deepcopy(self.eliminated_cards)
        for card in self.eliminated_cards:
            deck.get(card.name)

        number_of_players = self.number_of_players
        last_play = self.last_play
        player_turn = self.player_number
        table_cards_set = self.table_cards_set

        player_hands: list[Hand] = [Hand() for i in range(number_of_players)]

        for player_number in range(self.number_of_players):

            if player_number == self.player_number:

                player_hands[player_number].hand_stack = deepcopy(self.hand.hand_stack)
                for card in self.hand.hand_stack:
                    deck.get(card.name)

                table_stacks = []
                for table_stack_number in range(self.hand.table_stacks):
                    table_stack = TableStack(
                        top_card=None,
                        bottom_card=Card(suit="Spades", value="Ace"),  # this is a dummy card
                    )
                    table_stacks.append(table_stack)

                for i, card in enumerate(self.hand.table_stack):
                    table_stacks[i].top_card = card
                    deck.get(card.name)

                player_hands[player_number].table_stacks = table_stacks

            else:

                player_hands[player_number].hand_stack = deepcopy(
                    self.opponents[player_number].hand_stack
                )
                for card in self.opponents[player_number].hand_stack:
                    deck.get(card.name)

                table_stacks = []
                for table_stack_number in range(self.opponents[player_number].table_stacks):
                    table_stack = TableStack(
                        top_card=None,
                        bottom_card=Card(suit="Spades", value="Ace"),  # this is a dummy card
                    )
                    table_stacks.append(table_stack)

                for i, card in enumerate(self.opponents[player_number].table_stack):
                    table_stacks[i].top_card = card
                    deck.get(card.name)

                player_hands[player_number].table_stacks = table_stacks

        # set unknown cards
        for player_number in range(self.number_of_players):

            for table_stack in player_hands[player_number].table_stacks:
                card_list = deck.deal(num=1)
                table_stack.bottom_card = card_list[0]

            if player_number != self.player_number:
                card_list = deck.deal(num=self.opponents[player_number].hand_count_unknown)
                card_stack = Stack(cards=card_list)
                player_hands[player_number].hand_stack += card_stack

        assert len(deck) == self.deck_length

        game_state = GameState(
            deck=deck,
            discard_pile=discard_pile,
            eliminated_cards=eliminated_cards,
            player_hands=player_hands,
            last_play=last_play,
            number_of_players=number_of_players,
            player_turn=player_turn,
            table_cards_set=table_cards_set,
            win=None,
        )

        return game_state


def build_player_states(game_state: GameState) -> list[PlayerState]:

    opponents = dict()
    for i, player_hand in enumerate(game_state.player_hands):
        opponent = Opponent()
        opponent.hand_count_unknown = len(player_hand.hand_stack)
        opponent.table_stack = build_face_up_table_stack(table_stacks=player_hand.table_stacks)
        opponent.table_stacks = len(player_hand.table_stacks)
        opponents[i] = opponent

    player_states: list[PlayerState] = []

    for i, player_hand in enumerate(game_state.player_hands):

        player_state = PlayerState(player_number=i)

        player_state.discard_pile = deepcopy(game_state.discard_pile)
        player_state.last_play = game_state.last_play
        player_state.eliminated_cards = deepcopy(game_state.eliminated_cards)
        player_state.deck_length = len(game_state.deck)
        player_state.win = None
        player_state.number_of_players = game_state.number_of_players
        player_state.table_cards_set = game_state.table_cards_set

        player_state.opponents = deepcopy(opponents)

        del player_state.opponents[i]
        player_state.hand = PlayerHand()
        player_state.hand.hand_stack = deepcopy(player_hand.hand_stack)
        player_state.hand.table_stack = build_face_up_table_stack(
            table_stacks=player_hand.table_stacks
        )
        player_state.hand.table_stacks = len(player_hand.table_stacks)

        player_state.assert_conservation_of_cards()
        player_states.append(player_state)

    return player_states


def build_game(game_state: GameState, connection: Connection) -> Game:
    messaging = Messaging(number_of_players=game_state.number_of_players, connection=connection)
    game = Game(number_of_players=game_state.number_of_players, messaging=messaging)
    game.deck = game_state.deck
    game.discard_pile = game_state.discard_pile
    game.eliminated_cards = game_state.eliminated_cards
    game.player_hands = game_state.player_hands
    game.last_play = game_state.last_play
    game.number_of_players = game_state.number_of_players
    game.player_turn = game_state.player_turn
    game.win = game_state.win
    game.table_cards_set = game_state.table_cards_set
    game.assert_conservation_of_cards()

    return game
