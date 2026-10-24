FROM ubuntu:noble

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND=noninteractive

# install prerequisists
RUN apt-get update \
    && apt install -y \
      build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev curl git \
      libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev libyaml-dev \
      zip unzip vim wget lsb-release less sudo jq openssh-client

# ~/.ssh is mounted read-only from the host, so trust GitHub's published host keys
# system-wide, and push to GitHub over SSH (fetches stay on anonymous HTTPS)
RUN mkdir -p /etc/ssh \
    && curl -fsSL https://api.github.com/meta \
      | jq -r '.ssh_keys[] | "github.com " + .' > /etc/ssh/ssh_known_hosts \
    && test -s /etc/ssh/ssh_known_hosts \
    && git config --system url."git@github.com:".pushInsteadOf "https://github.com/"

ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000
ARG USER_HOME=/home/dev

# The container user mirrors the host user (name, uid, home path) so that
# ~/.claude (sessions, memory, plugin cache with absolute paths) works unchanged.
RUN if id -u ubuntu >/dev/null 2>&1; then userdel -r ubuntu; fi \
    && groupadd --gid "$USER_GID" "$USERNAME" \
    && mkdir -p "$(dirname "$USER_HOME")" \
    && useradd --uid "$USER_UID" --gid "$USER_GID" --create-home --home-dir "$USER_HOME" --shell /bin/bash "$USERNAME" \
    && echo "$USERNAME ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME" \
    && chmod 0440 "/etc/sudoers.d/$USERNAME"

USER ${USERNAME}

# install python things
ARG PYTHON_VERSION=3.13
ARG POETRY_VERSION=2.1.3

ENV PYENV_ROOT="${USER_HOME}/.pyenv"
ENV PATH="${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:${USER_HOME}/.local/bin:$PATH"
RUN curl https://pyenv.run | bash \
    && pyenv install ${PYTHON_VERSION} \
    && pyenv global ${PYTHON_VERSION} \
    && pip install pre-commit \
    && pip install poetry==${POETRY_VERSION}

# install ruby things
ARG RUBY_VERSION=3.4.1
ARG TRMNLP_VERSION=0.5.6

ENV RBENV_ROOT="${USER_HOME}/.rbenv"
ENV PATH="${RBENV_ROOT}/shims:${RBENV_ROOT}/bin:$PATH"
RUN git clone https://github.com/rbenv/rbenv.git ${RBENV_ROOT} \
    && git clone https://github.com/rbenv/ruby-build.git ${RBENV_ROOT}/plugins/ruby-build \
    && echo 'eval "$(rbenv init -)"' >> ${USER_HOME}/.bashrc \
    && rbenv install ${RUBY_VERSION} \
    && rbenv global ${RUBY_VERSION} \
    && rbenv rehash \
    && gem update --system \
    && gem install trmnl_preview -v ${TRMNLP_VERSION}

# install claude code (native installer, user-owned so auto-updates work).
# ~/.claude and ~/.claude.json are bind-mounted from the host (see devcontainer.json).
RUN curl -fsSL https://claude.ai/install.sh | bash
