# This is a simulation of a card game called Screw

## Background
My childhood was full of card games and I still regularly play card games with friends. A group of my friends play this game called "Screw" (although they call if "FU", https://en.wikipedia.org/wiki/Screw_(card_game)). I thought it would be fun to build a computer AI that plays the game. So far, I've implemented the game manager and communication protocols.

This is a work in progress, and I haven't had any code review.

## Notes on Structure and Setup

This game manager uses a simple distributed systems setup. The `main.py` script runs the game in a subprocess and routes communication between players using ZeroMQ. An isolated communication channel is maintained with each player. Each player (human or computer) acts as a server and the communication router uses a Request-Respond architecture for communicating with each player. The communication and routing is intentionally created with an "arms-length" interaction. This means that the game does not know (or care) if the player is a computer or human.

The `console_player.py` script is used for a human player to play the game. This script should run in a separate terminal for each human player that wants to play.

The `Game` class in `game.py` manages the administration of the game and communicates exclusively through the `Messaging` class.

The `Messaging` class in `messaging.py` is used for standardizing and encoding messaging between the game and players. The messaging layer creates abstraction between the game and the players. Because of this abstraction, the game can be played live by a human or computer, or can be used for by search and ML algorithms for scenario simulation.

I have not tried to optImize the user interface for human players. The only reasons to have a human player interface are 1) for QA testing the game and 2) to play against the computer. Screw is more pleasant to play with actual cards.

## Build and Run Commands

### Build Game Docker Image
`docker-compose build game-runner`

### Lint and Test
`docker-compose run --rm game-runner bash -c "just lint"`
`docker-compose run --rm game-runner bash -c "just unit-test"`

### Run Game Manager
Make sure all players are running before the game manager is started.
`docker-compose run --rm game-runner bash -c "just run-game {{number of players}}"`

### Run Player
`docker-compose run --name player{{x}} --rm game-runner bash -c "just run-player"`
where x = player number, starting from one. The name parameter is required because it is the player server name in the docker virtual network. Player numbers must be sequestial, i.e. for a game with three players, player numbers would be 1, 2, and 3.

For example, player two will run the following command in their terminal.
`docker-compose run --name player2 --rm game-runner bash -c "just run-player"`

## Technologies Used

### Docker
I use Docker to allow for cross-platform development and usage. I'm developing on Windows but prefer using a Unix environment. I'm using only one Docker image right now. Although, that could be split between human player, computer player, testing, and game manager.

### ZeroMQ
I use ZeroMQ to facilitate messaging between the game runner, human players, and computer players.

### Poetry
I prefer Poetry to requirements.txt for dependency management.

### Just
Just, and the recipes in justfile, are great for managing command-line operations.

### Linting: Mypy, Black, Flake8
I use all three libraries for linting.

### Pytest
I use Pytest for unit and integration testing.

### Pydantic
Pydantic serializes and deserializes objects that are passed between processes.

### PyDealer
PyDealer is a Python package that simulates standard playing cards. I use PyDealer extensively.
https://pydealer.readthedocs.io/en/latest/
