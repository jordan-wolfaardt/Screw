FROM python:3.10

#SHELL ["/bin/bash", "-l", "-c"]
SHELL ["/bin/bash", "-c"]

RUN apt-get -y update \
    && apt-get -y install curl \
    && apt-get -y install unzip \
    && apt-get -y autoremove

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_HOME="/etc/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VERSION=1.2.1

RUN mkdir -p ~/bin
RUN curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/bin
ENV PATH="$PATH:/root/bin"

ENV POETRY_PATH="${POETRY_HOME}/bin/poetry"

WORKDIR game

RUN curl -sSL https://install.python-poetry.org | python3 -
RUN cd /usr/local/bin && ln -s ${POETRY_PATH} && chmod +x ${POETRY_PATH}

EXPOSE 5000

COPY ./pyproject.toml ./
RUN poetry config virtualenvs.create true \
    && poetry install -vvv --no-interaction --no-ansi --no-root

COPY . ./

ENV PYTHONPATH=${PYTHONPATH}:/src
