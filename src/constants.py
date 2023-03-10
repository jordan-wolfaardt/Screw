TABLE_STACKS = 3
HAND_CARDS = 3
MIN_PLAYERS = 2
MAX_PLAYERS = 4

DECK_LEN = 52

ENCODE_SUIT = {
    "Diamonds": "D",
    "Clubs": "C",
    "Hearts": "H",
    "Spades": "S",
}

DECODE_SUIT = {
    "D": "Diamonds",
    "C": "Clubs",
    "H": "Hearts",
    "S": "Spades",
}

ENCODE_VALUE = {
    "2": "2",
    "3": "3",
    "4": "4",
    "5": "5",
    "6": "6",
    "7": "7",
    "8": "8",
    "9": "9",
    "10": "T",
    "Jack": "J",
    "Queen": "Q",
    "King": "K",
    "Ace": "A",
}

DECODE_VALUE = {
    "2": "2",
    "3": "3",
    "4": "4",
    "5": "5",
    "6": "6",
    "7": "7",
    "8": "8",
    "9": "9",
    "T": "10",
    "J": "Jack",
    "Q": "Queen",
    "K": "King",
    "A": "Ace",
}

PLAY_RANKS = {
    "T": 12,
    "2": 11,
    "A": 10,
    "K": 9,
    "Q": 8,
    "J": 7,
    "9": 6,
    "8": 5,
    "7": 4,
    "6": 3,
    "5": 2,
    "4": 1,
    "3": 0,
}
