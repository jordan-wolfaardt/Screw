import copy
import json
from contextlib import nullcontext
from multiprocessing import Pipe
from random import randint
from typing import Optional

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pydealer import (  # type: ignore
    Card,
    Stack,
)

from src.constants import DECK_LEN
from src.exceptions import CardEncodeDecodeException, CardsNotAvailableException
from src.game import (
    Action,
    Game,
    HAND_CARDS,
    MAX_PLAYERS,
    MIN_PLAYERS,
    Play,
    TABLE_STACKS,
    TableStack,
)
from src.game_types import RequestType, Response
from src.messaging import Messaging
from src.utilities import (
    build_face_up_table_stack,
    deserialize_card,
    deserialize_cards,
    serialize_cards,
)


@pytest.fixture
def mock_messaging(monkeypatch: MonkeyPatch) -> Messaging:
    number_of_players = MAX_PLAYERS - 1
    connection, _ = Pipe(duplex=True)
    monkeypatch.setattr(connection, "recv", lambda: {"success": True})
    monkeypatch.setattr(connection, "send", lambda body: None)
    messaging = Messaging(number_of_players=number_of_players, connection=connection)
    return messaging


def raise_(ex):
    raise ex


def valid_response() -> Response:
    response = Response(action=Action.SET_TABLE_CARDS, cards=json.dumps(["H2", "C5"]))
    return response


@pytest.fixture
def game(monkeypatch: MonkeyPatch, mock_messaging: Messaging) -> Game:
    number_of_players = randint(MIN_PLAYERS, MAX_PLAYERS)
    game = Game(number_of_players=number_of_players, messaging=mock_messaging)
    monkeypatch.setattr(game, "messaging", mock_messaging)
    return game


def get_cards_from_player(player_number: int, game: Game, count: int) -> Response:
    game = copy.deepcopy(game)
    game.initial_deal()
    stack = Stack(cards=game.player_hands[player_number].hand_stack.deal(num=count))
    serialized_response = serialize_cards(stack)
    return Response(action=Action.SET_TABLE_CARDS, cards=serialized_response)


class TestGame:
    @pytest.mark.parametrize(
        "number_of_players,raises",
        [
            (MIN_PLAYERS - 1, pytest.raises(AssertionError)),
            (randint(MIN_PLAYERS, MAX_PLAYERS), nullcontext()),
            (3, nullcontext()),
            (MAX_PLAYERS + 1, pytest.raises(AssertionError)),
        ],
    )
    def test_init(
        self, number_of_players: int, raises: nullcontext, mock_messaging: Messaging
    ) -> None:

        with raises:
            game = Game(number_of_players=number_of_players, messaging=mock_messaging)

            assert game.number_of_players == number_of_players
            assert game.player_turn == 0
            assert game.number_of_players == number_of_players
            game.assert_conservation_of_cards()

    def test_setup(self, monkeypatch: MonkeyPatch, game: Game, mock_messaging: Messaging) -> None:

        game_copy = copy.deepcopy(game)

        monkeypatch.setattr(game.deck, "shuffle", lambda: None)

        game.messaging, "request", lambda player_number, request_type: Response(
            action=Action.PLAY_KNOWN_CARDS, cards="S3,H3"
        )
        monkeypatch.setattr(
            game.messaging,
            "request",
            lambda player_number, request_type: get_cards_from_player(
                player_number=player_number, game=game_copy, count=3
            ),
        )

        game.setup()

        assert len(game.deck) == DECK_LEN - (
            (HAND_CARDS + (TABLE_STACKS * 2)) * game.number_of_players
        )
        game.assert_conservation_of_cards()

        for player_hand in game.player_hands:
            assert len(player_hand.table_stacks) == TABLE_STACKS
            assert len(player_hand.hand_stack) == HAND_CARDS

            for table_stack in player_hand.table_stacks:
                assert table_stack.top_card is not None

    def test_initial_deal(self, game: Game) -> None:

        game.initial_deal()

        assert len(game.player_hands) == game.number_of_players

        assert len(game.deck) == DECK_LEN - (
            (HAND_CARDS + (TABLE_STACKS * 2)) * game.number_of_players
        )
        game.assert_conservation_of_cards()

        for player_hand in game.player_hands:
            assert len(player_hand.table_stacks) == TABLE_STACKS
            assert len(player_hand.hand_stack) == HAND_CARDS + TABLE_STACKS

            for table_stack in player_hand.table_stacks:
                assert table_stack.top_card is None

    def test_set_table_cards(self, monkeypatch: MonkeyPatch, mock_messaging: Messaging) -> None:

        number_of_players = 2

        game = Game(number_of_players=number_of_players, messaging=mock_messaging)

        game.initial_deal()

        bottom_card = Card(suit="Hearts", value="Ace")
        card1 = Card(suit="Spades", value="Ace")
        card2 = Card(suit="Spades", value="2")
        card3 = Card(suit="Spades", value="3")
        card4 = Card(suit="Spades", value="4")
        card5 = Card(suit="Spades", value="5")
        card6 = Card(suit="Spades", value="6")

        def mock_request_set_table_cards(player_number: int) -> Response:
            response: Response
            if player_number == 0:
                response = Response(
                    action=Action.SET_TABLE_CARDS,
                    cards=serialize_cards(Stack(cards=[card1, card2, card3])),
                )
            elif player_number == 1:
                response = Response(
                    action=Action.SET_TABLE_CARDS,
                    cards=serialize_cards(Stack(cards=[card4, card5, card6])),
                )
            return response

        monkeypatch.setattr(game, "messaging", mock_messaging)
        monkeypatch.setattr(
            game.messaging,
            "request",
            lambda player_number, request_type: mock_request_set_table_cards(
                player_number=player_number
            ),
        )

        for player_hand in game.player_hands:
            player_hand.table_stacks.append(TableStack(bottom_card=bottom_card))

        game.player_hands[0].hand_stack += Stack(cards=[card1])
        game.player_hands[0].hand_stack += Stack(cards=[card2])
        game.player_hands[0].hand_stack += Stack(cards=[card3])

        game.player_hands[1].hand_stack += Stack(cards=[card4])
        game.player_hands[1].hand_stack += Stack(cards=[card5])
        game.player_hands[1].hand_stack += Stack(cards=[card6])

        stack1 = Stack(cards=[card1, card2, card3])
        stack2 = Stack(cards=[card4, card5, card6])

        stack1.sort()
        stack2.sort()

        game.set_table_cards()

        player_0_face_up_cards = build_face_up_table_stack(
            table_stacks=game.player_hands[0].table_stacks
        )
        player_1_face_up_cards = build_face_up_table_stack(
            table_stacks=game.player_hands[1].table_stacks
        )

        player_0_face_up_cards.sort()
        player_1_face_up_cards.sort()

        assert stack1 == player_0_face_up_cards
        assert stack2 == player_1_face_up_cards

    def test_loop_until_valid_table_cards(self, game: Game, monkeypatch: MonkeyPatch) -> None:

        bottom_card = Card(suit="Hearts", value="Ace")
        card1 = Card(suit="Spades", value="4")
        card2 = Card(suit="Spades", value="2")
        card3 = Card(suit="Spades", value="3")

        player_number = randint(0, game.number_of_players - 1)

        monkeypatch.setattr(
            game.messaging,
            "request",
            lambda player_number, request_type: Response(
                action=Action.SET_TABLE_CARDS, cards="S2,S3,S4"
            ),
        )

        game.player_hands[player_number].table_stacks.append(TableStack(bottom_card=bottom_card))

        game.player_hands[player_number].hand_stack += Stack(cards=[card1])
        game.player_hands[player_number].hand_stack += Stack(cards=[card2])
        game.player_hands[player_number].hand_stack += Stack(cards=[card3])

        stack = Stack(cards=[card1, card2, card3])

        stack.sort()

        game.deal_table_cards()
        game.loop_until_valid_table_cards(player_number=player_number)

        face_up_cards = build_face_up_table_stack(
            table_stacks=game.player_hands[player_number].table_stacks
        )

        face_up_cards.sort()

        assert stack == face_up_cards

    @pytest.mark.parametrize(
        "response_cards,expected_success",
        [
            ("S2,S3,S4", True),
            ("S2,S2,S3", False),
            ("S2,S3", False),
            ("S2,S3,S4,S5", False),
            ("S2,S3,P4", False),
            ("S2,S35,S4", False),
            ("S2,S3,H4", False),
        ],
    )
    def test_handle_table_card_selection(
        self,
        game: Game,
        monkeypatch: MonkeyPatch,
        response_cards: str,
        expected_success: bool,
    ) -> None:

        bottom_card = Card(suit="Hearts", value="Ace")
        card1 = Card(suit="Spades", value="4")
        card2 = Card(suit="Spades", value="2")
        card3 = Card(suit="Spades", value="3")

        player_number = randint(0, game.number_of_players - 1)

        monkeypatch.setattr(
            game.messaging,
            "request",
            lambda player_number, request_type: Response(
                action=Action.SET_TABLE_CARDS, cards=response_cards
            ),
        )

        game.initial_deal()

        game.player_hands[player_number].table_stacks.append(TableStack(bottom_card=bottom_card))

        game.player_hands[player_number].hand_stack += Stack(cards=[card1])
        game.player_hands[player_number].hand_stack += Stack(cards=[card2])
        game.player_hands[player_number].hand_stack += Stack(cards=[card3])

        stack = Stack(cards=[card1, card2, card3])

        stack.sort()

        success = game.handle_table_card_selection(player_number=player_number)

        assert success == expected_success

        if success:
            face_up_cards = build_face_up_table_stack(
                table_stacks=game.player_hands[player_number].table_stacks
            )

            face_up_cards.sort()

            assert stack == face_up_cards

    @pytest.mark.parametrize(
        "response_cards,raises",
        [
            ("S2,S3,S4", nullcontext()),
            ("S2,S2,S3", pytest.raises(AssertionError)),
            ("S2,S3", pytest.raises(AssertionError)),
            ("S2,S3,S4,S5", pytest.raises(AssertionError)),
            ("S2,S3,P4", pytest.raises(CardEncodeDecodeException)),
            ("S2,S35,S4", pytest.raises(CardEncodeDecodeException)),
            ("S2,S3,H4", pytest.raises(CardsNotAvailableException)),
        ],
    )
    def test_receive_table_card_selection(
        self, game: Game, response_cards: str, raises: nullcontext, monkeypatch: MonkeyPatch
    ) -> None:

        card1 = Card(suit="Spades", value="Ace")
        card2 = Card(suit="Spades", value="2")
        card3 = Card(suit="Spades", value="3")
        card4 = Card(suit="Spades", value="4")
        card5 = Card(suit="Spades", value="5")
        card6 = Card(suit="Spades", value="6")

        hand_stack = Stack(cards=[card1, card2, card3, card4, card5, card6])

        game.deal_table_cards()

        game.player_hands[0].hand_stack = hand_stack

        monkeypatch.setattr(
            game.messaging,
            "request",
            lambda player_number, request_type: Response(
                action=Action.SET_TABLE_CARDS, cards=response_cards
            ),
        )

        with raises:
            game.receive_table_card_selection(player_number=0)
            assert len(game.player_hands[0].hand_stack) == 3
            for table_stack in game.player_hands[0].table_stacks:
                assert table_stack.top_card is not None

    def test_place_table_cards(self, game: Game) -> None:

        card1 = Card(suit="Spades", value="Ace")
        card2 = Card(suit="Spades", value="2")
        card3 = Card(suit="Spades", value="3")

        stack = Stack(cards=[card1, card2, card3])

        game.initial_deal()

        for player_hand in game.player_hands:
            for table_stack in player_hand.table_stacks:
                assert table_stack.top_card is None

        game.place_table_cards(player_number=0, stack=stack)

        player_0_face_up_cards = build_face_up_table_stack(
            table_stacks=game.player_hands[0].table_stacks
        )

        stack.sort()
        player_0_face_up_cards.sort()

        assert stack == player_0_face_up_cards

    def test_deal_table_cards(self, game: Game) -> None:

        game.deal_table_cards()

        assert len(game.deck) == DECK_LEN - (TABLE_STACKS * game.number_of_players)
        game.assert_conservation_of_cards()

        for player_hand in game.player_hands:
            assert len(player_hand.table_stacks) == TABLE_STACKS

            for table_stack in player_hand.table_stacks:
                assert table_stack.top_card is None

    def test_deal_table_card(self, game: Game) -> None:

        player_number = randint(0, game.number_of_players - 1)

        game.deal_table_card(player_number=player_number)

        assert game.player_hands[player_number].table_stacks[0].bottom_card
        assert len(game.deck) == DECK_LEN - 1
        game.assert_conservation_of_cards()

    def test_deal_hand_cards(self, game: Game) -> None:

        game.deal_hand_cards()

        assert len(game.deck) == DECK_LEN - ((HAND_CARDS + TABLE_STACKS) * game.number_of_players)
        game.assert_conservation_of_cards()

        for player_hand in game.player_hands:
            assert len(player_hand.hand_stack) == HAND_CARDS + TABLE_STACKS

    def test_deal_card(self, game: Game) -> None:

        player_number = randint(0, game.number_of_players - 1)

        game.deal_card(player_number=player_number)

        assert len(game.player_hands[player_number].hand_stack) == 1
        assert len(game.deck) == DECK_LEN - 1
        game.assert_conservation_of_cards()

        # empty deck scenario
        game.deck = Stack()
        game.deal_card(player_number=player_number)
        assert len(game.player_hands[player_number].hand_stack) == 1

    def test_run(self, game: Game, monkeypatch: MonkeyPatch) -> None:

        player_number = randint(0, game.number_of_players - 1)

        game.deal_card(player_number=player_number)

        monkeypatch.setattr(
            game.messaging,
            "request",
            lambda player_number, request_type: Response(
                action=Action.PLAY_KNOWN_CARDS,
                cards=serialize_cards(game.player_hands[player_number].hand_stack),
            ),
        )

        game.player_turn = player_number

        game.run()

    @pytest.mark.parametrize(
        "count,expected_player_turn",
        [
            (1, 1),
            (3, 0),
            (4, 1),
        ],
    )
    def test_update_turn(self, game: Game, count: int, expected_player_turn: int) -> None:
        game.number_of_players = 3
        game.update_turn(count=count)
        assert game.player_turn == expected_player_turn

    def test_loop_until_valid_play(self, game: Game, monkeypatch: MonkeyPatch) -> None:

        monkeypatch.setattr(
            game.messaging,
            "request",
            lambda player_number, request_type: Response(
                action=Action.PLAY_KNOWN_CARDS, cards="S3,H3"
            ),
        )

        player_number = randint(0, game.number_of_players - 1)

        card1 = Card(suit="Spades", value="3")
        card2 = Card(suit="Hearts", value="3")

        game.player_hands[player_number].hand_stack = Stack(cards=[card1, card2])

        game.loop_until_valid_play(player_number=player_number)

    @pytest.mark.parametrize(
        "raises_bool,exception,raises",
        [
            (False, Exception, nullcontext()),
            (True, CardsNotAvailableException, pytest.raises(CardsNotAvailableException)),
            (True, Exception, pytest.raises(Exception)),
        ],
    )
    def test_get_valid_play(
        self,
        game: Game,
        raises_bool: bool,
        exception: Exception,
        raises: nullcontext,
        monkeypatch: MonkeyPatch,
    ) -> None:

        monkeypatch.setattr(
            game,
            "receive_and_validate_play",
            lambda player_number: Play(action=Action.PICK_UP_DISCARD_PILE)
            if not raises_bool
            else raise_(exception),
        )

        monkeypatch.setattr(game, "update_game_state_for_play", lambda player_number, play: None)

        if raises_bool:
            assert game.get_valid_play(player_number=0) is False
        else:
            assert game.get_valid_play(player_number=0) is True

    @pytest.mark.parametrize(
        "hand_cards,expected_action",
        [
            (Stack(cards=[Card(value="2", suit="Diamonds")]), Action.PLAY_KNOWN_CARDS),
            (Stack(), Action.PLAY_FACE_DOWN),
        ],
    )
    def test_receive_and_validate_play(
        self, game: Game, hand_cards: Stack, expected_action: Action, monkeypatch: MonkeyPatch
    ) -> None:
        response = Response(action=Action.PLAY_KNOWN_CARDS, cards="D2")
        monkeypatch.setattr(
            game.messaging,
            "request",
            lambda player_number, request_type: response,
        )
        player_number = 0
        game.deal_table_cards()
        game.discard_pile = Stack(cards=[Card(value="2", suit="Spades")])
        game.player_hands[player_number].hand_stack = hand_cards
        play = game.receive_and_validate_play(player_number=player_number)
        assert play.action == expected_action

    @pytest.mark.parametrize(
        "serialized_response,expected",
        [
            (valid_response(), nullcontext()),
            ({}, pytest.raises(Exception)),
        ],
    )
    def test_handle_request(
        self,
        game: Game,
        serialized_response: dict,
        expected: nullcontext,
        monkeypatch: MonkeyPatch,
    ) -> None:

        monkeypatch.setattr(
            game.messaging,
            "request",
            lambda player_number, request_type: serialized_response,
        )

        with expected:
            assert game.handle_request(player_number=0, request_type=RequestType.PLAY)

    @pytest.mark.parametrize(
        "play,discard_pile,last_play,hand_stack,expected",
        [
            (Play(action=Action.SET_TABLE_CARDS), "", "", "", pytest.raises(AssertionError)),
            (Play(action=Action.PICK_UP_DISCARD_PILE), "H3,S3", "", "", nullcontext()),
            (Play(action=Action.PICK_UP_DISCARD_PILE), "", "", "", pytest.raises(AssertionError)),
            (
                Play(action=Action.PLAY_KNOWN_CARDS, cards=Stack()),
                "",
                "",
                "",
                pytest.raises(AssertionError),
            ),
            (
                Play(
                    action=Action.PLAY_KNOWN_CARDS,
                    cards=Stack(
                        cards=[Card(suit="Spades", value="3"), Card(suit="Spades", value="4")]
                    ),
                ),
                "",
                "",
                "",
                pytest.raises(AssertionError),
            ),
            (
                Play(
                    action=Action.PLAY_KNOWN_CARDS,
                    cards=Stack(cards=[Card(suit="Spades", value="3")]),
                ),
                "",
                "S4",
                "S3",
                pytest.raises(AssertionError),
            ),
            (
                Play(
                    action=Action.PLAY_KNOWN_CARDS,
                    cards=Stack(cards=[Card(suit="Spades", value="4")]),
                ),
                "",
                "S3",
                "S4",
                nullcontext(),
            ),
        ],
    )
    def test_validate_play(
        self,
        game: Game,
        play: Play,
        discard_pile: str,
        last_play: str,
        hand_stack: str,
        expected: nullcontext,
    ) -> None:

        game.discard_pile = deserialize_cards(discard_pile)
        game.last_play = deserialize_cards(last_play)
        game.player_hands[0].hand_stack = deserialize_cards(hand_stack)

        with expected:
            game.validate_play(play=play, player_number=0)

    @pytest.mark.parametrize(
        "bottom_card,last_play,play_face_down_success",
        [
            (
                Card(suit="Diamonds", value="9"),
                Stack(cards=[Card(suit="Diamonds", value="8")]),
                True,
            ),
            (
                Card(suit="Diamonds", value="8"),
                Stack(cards=[Card(suit="Diamonds", value="9")]),
                False,
            ),
        ],
    )
    def test_handle_face_down_play(
        self, game: Game, bottom_card: Card, last_play: Stack, play_face_down_success
    ) -> None:

        player_number = 0
        game.player_hands[player_number].table_stacks = [TableStack(bottom_card=bottom_card)]
        game.last_play = last_play
        game.discard_pile = deserialize_cards("S2")

        game.handle_face_down_play(player_number=player_number)

        if play_face_down_success:
            assert len(game.player_hands[player_number].table_stacks) == 0
        else:
            assert len(game.discard_pile) == 0

    def test_pickup_discard_pile(self, game: Game) -> None:
        player_number = 0
        game.discard_pile = deserialize_cards("H2")
        game.last_play = deserialize_cards("H2")
        game.pickup_discard_pile(player_number=player_number)
        assert game.player_hands[player_number].hand_stack == deserialize_cards("H2")
        assert game.last_play is None
        assert game.player_turn == 1

    @pytest.mark.parametrize(
        "top_card,last_play,play_face_down_success",
        [
            (
                Card(suit="Diamonds", value="9"),
                Stack(cards=[Card(suit="Diamonds", value="8")]),
                True,
            ),
            (
                Card(suit="Diamonds", value="8"),
                Stack(cards=[Card(suit="Diamonds", value="9")]),
                False,
            ),
        ],
    )
    def test_handle_face_up_play(
        self, game: Game, top_card: Card, last_play: Stack, play_face_down_success
    ) -> None:

        player_number = 0
        game.player_hands[player_number].table_stacks = [
            TableStack(bottom_card=deserialize_card(card_code="H2"), top_card=top_card)
        ]
        game.last_play = last_play
        game.discard_pile = deserialize_cards("S2")

        game.handle_face_up_play(player_number=player_number, cards_played=Stack(cards=[top_card]))

        if play_face_down_success:
            assert game.player_hands[player_number].table_stacks[0].top_card is None
        else:
            assert len(game.discard_pile) == 0

    @pytest.mark.parametrize(
        "play,encoded_hand_cards",
        [
            (Play(action=Action.PICK_UP_DISCARD_PILE), ""),
            (
                Play(
                    action=Action.PLAY_FACE_DOWN,
                    cards=Stack(cards=[Card(suit="Diamonds", value="3")]),
                ),
                "",
            ),
            (
                Play(
                    action=Action.PLAY_KNOWN_CARDS,
                    cards=Stack(cards=[Card(suit="Diamonds", value="9")]),
                ),
                "D9",
            ),
            (
                Play(
                    action=Action.PLAY_KNOWN_CARDS,
                    cards=Stack(cards=[Card(suit="Diamonds", value="3")]),
                ),
                "",
            ),
        ],
    )
    def test_update_game_state_for_play(
        self, game: Game, play: Play, encoded_hand_cards: str
    ) -> None:

        player_number = 0
        discard_pile = Stack(
            cards=[Card(suit="Diamonds", value="7"), Card(suit="Diamonds", value="8")]
        )
        game.discard_pile = copy.deepcopy(discard_pile)
        game.player_hands[player_number].hand_stack = deserialize_cards(
            encoded_cards=encoded_hand_cards
        )
        game.last_play = deserialize_cards(encoded_cards="H5")

        table_stack = TableStack(
            bottom_card=Card(value="4", suit="Hearts"),
        )

        game.player_hands[player_number].table_stacks = [table_stack]

        game.update_game_state_for_play(play=play, player_number=player_number)

        if play.action == Action.PLAY_KNOWN_CARDS and len(encoded_hand_cards) > 0:
            assert len(game.player_hands[player_number].hand_stack) == 1
        elif play.action == Action.PLAY_FACE_DOWN:
            assert len(game.discard_pile) == 0
            assert len(game.player_hands[player_number].hand_stack) == len(discard_pile) + 1
        else:
            assert len(game.discard_pile) == 0
            assert len(game.player_hands[player_number].hand_stack) == len(discard_pile)

    @pytest.mark.parametrize(
        "played_cards,encoded_hand_cards",
        [
            ("H5", ""),
            ("HT", "H6"),
            ("H4", "H6"),
            ("H7", "H6"),
        ],
    )
    def test_play_cards(self, game: Game, played_cards: str, encoded_hand_cards: str) -> None:

        player_number = 0
        game.last_play = deserialize_cards(encoded_cards="S7")

        game.player_hands[player_number].hand_stack = deserialize_cards(
            encoded_cards=encoded_hand_cards
        )
        game.play_cards(
            player_number=player_number, cards=deserialize_cards(encoded_cards=played_cards)
        )

        if len(encoded_hand_cards) == 0:
            assert game.win == player_number
            assert len(game.eliminated_cards) == 0
        elif played_cards == "HT":
            assert game.win is None
            assert len(game.eliminated_cards) > 0
            assert game.player_turn == 0
        elif played_cards == "H7":
            assert game.win is None
            assert len(game.eliminated_cards) == 0
            assert game.player_turn == 2 % game.number_of_players
        else:
            assert game.win is None
            assert len(game.eliminated_cards) == 0
            assert game.player_turn == 1

    @pytest.mark.parametrize(
        "encoded_last_play",
        [
            "HT",
            "H4",
            "H5",
        ],
    )
    def test_check_for_burn(self, game: Game, encoded_last_play: str) -> None:
        game.discard_pile = deserialize_cards(encoded_cards="D4,C4,S4," + encoded_last_play)
        game.last_play = deserialize_cards(encoded_cards=encoded_last_play)
        if encoded_last_play == "HT":
            assert game.check_for_burn() is True
        elif encoded_last_play == "H4":
            assert game.check_for_burn() is True
        elif encoded_last_play == "H5":
            assert game.check_for_burn() is False

    @pytest.mark.parametrize(
        "hand_stack,cards,raises",
        [
            (
                Stack(cards=[Card(value="9", suit="Hearts"), Card(value="8", suit="Hearts")]),
                Stack(cards=[Card(value="9", suit="Hearts")]),
                nullcontext(),
            ),
            (
                Stack(),
                Stack(cards=[Card(value="9", suit="Hearts")]),
                pytest.raises(CardsNotAvailableException),
            ),
        ],
    )
    def test_remove_cards_from_hand_stack(
        self, game: Game, hand_stack: Stack, cards: Stack, raises: nullcontext
    ) -> None:

        player_number = 0
        game.player_hands[player_number].hand_stack = copy.deepcopy(hand_stack)

        with raises:
            game.remove_cards_from_hand_stack(player_number=player_number, cards=cards)

            assert len(game.player_hands[player_number].hand_stack) == 1

    @pytest.mark.parametrize(
        "table_stacks,cards,raises",
        [
            (
                [
                    TableStack(
                        bottom_card=Card(value="8", suit="Hearts"),
                        top_card=Card(value="9", suit="Hearts"),
                    ),
                    TableStack(
                        bottom_card=Card(value="8", suit="Hearts"),
                        top_card=Card(value="7", suit="Hearts"),
                    ),
                ],
                Stack(cards=[Card(value="9", suit="Hearts"), Card(value="7", suit="Hearts")]),
                nullcontext(),
            ),
            (
                [TableStack(bottom_card=Card(value="8", suit="Hearts"))],
                Stack(cards=[Card(value="9", suit="Hearts")]),
                pytest.raises(CardsNotAvailableException),
            ),
        ],
    )
    def test_remove_cards_from_face_up(
        self,
        game: Game,
        table_stacks: Optional[list[TableStack]],
        cards: Stack,
        raises: nullcontext,
    ) -> None:

        player_number = 0
        if table_stacks is not None:
            assert table_stacks
            game.player_hands[player_number].table_stacks = copy.deepcopy(table_stacks)

        with raises:
            game.remove_cards_from_face_up(player_number=player_number, cards=cards)
            assert game.player_hands[player_number].table_stacks[0].top_card is None

    @pytest.mark.parametrize(
        "hand_stack,table_stacks,expected_result",
        [
            (Stack(), [TableStack(bottom_card=Card(value="8", suit="Hearts"))], False),
            (
                Stack(cards=[Card(value="9", suit="Hearts"), Card(value="8", suit="Hearts")]),
                [],
                False,
            ),
            (Stack(), [], True),
        ],
    )
    def test_check_victory(
        self,
        game: Game,
        hand_stack: Stack,
        table_stacks: list[TableStack],
        expected_result: bool,
    ) -> None:

        player_number = 0
        game.player_hands[player_number].hand_stack = copy.deepcopy(hand_stack)

        game.player_hands[player_number].table_stacks = copy.deepcopy(table_stacks)

        assert game.check_victory(player_number=player_number) == expected_result

    @pytest.mark.parametrize(
        "card,raises",
        [
            (None, nullcontext()),
            (Card(value="8", suit="Hearts"), pytest.raises(AssertionError)),
        ],
    )
    def test_assert_conservation_of_cards(
        self, game: Game, card: Optional[Card], raises: nullcontext
    ) -> None:

        game.assert_conservation_of_cards()

        with raises:
            if card is not None:
                game.player_hands[0].hand_stack += Stack(cards=[card])
            game.deal_card(player_number=0)
            game.assert_conservation_of_cards()
