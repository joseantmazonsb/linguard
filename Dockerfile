FROM python:3.9-slim-bullseye as python-base
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.1.11 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

FROM python-base as builder-base
WORKDIR $PYSETUP_PATH
COPY poetry.lock pyproject.toml ./
RUN pip install "poetry==$POETRY_VERSION" &&\
    poetry install --no-dev

FROM python-base as production
RUN apt-get update && \
    apt-get install -y --no-install-recommends wireguard-tools iptables libpcre3 uwsgi uwsgi-plugin-python3 sudo iproute2 && \
    useradd -ms /bin/bash linguard && \
    echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg" > /etc/sudoers.d/linguard && \
    echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg-quick" >> /etc/sudoers.d/linguard

COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH
COPY config/linguard.sample.yaml /etc/linguard/config/linguard.yaml
COPY config/uwsgi.sample.yaml /etc/linguard/config/uwsgi.yaml
COPY linguard /var/www/linguard/linguard
RUN ln -s  $VENV_PATH /var/www/linguard/venv && \
    mkdir -p /var/log/linguard/ && \
    chown -R linguard:linguard /etc/linguard && \
    chown linguard:linguard /var/www/linguard && \
    chown -R linguard:linguard /var/www/linguard && \
    chown linguard:linguard /var/log/linguard && \
    chmod +x -R "/var/www/linguard/linguard/core/tools"
WORKDIR /var/www/linguard/linguard
USER linguard
CMD [ "/usr/bin/uwsgi", "--yaml", "/etc/linguard/config/uwsgi.yaml"]