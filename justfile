
default:
    just --list


format-black:
  poetry run black .


lint-black:
  poetry run black --check .


lint-flake8:
  poetry run flake8


lint-mypy:
  poetry run mypy . --explicit-package-bases --namespace-packages


lint: lint-black lint-flake8 lint-mypy


unit-test:
  #!/usr/bin/env bash
  export PYTHONPATH=$PYTHONPATH:$PWD/src;
  poetry run pytest test/unit --disable-warnings -v -s


run-game number-of-players:
  #!/usr/bin/env bash
  poetry run python src/main.py {{number-of-players}}


run-player player-number player-type:
  #!/usr/bin/env bash
  poetry run python src/console_player.py {{player-number}} {{player-type}}
