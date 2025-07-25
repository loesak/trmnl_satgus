FROM ubuntu:noble

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND=noninteractive

# install prerequisists
RUN apt-get update \
    && apt install -y \
      build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev curl git \
      libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev libyaml-dev \
      zip unzip vim wget lsb-release less

ARG USER=ubuntu
ARG HOME="/home/${USER}"

# install python things
ARG PYTHON_VERSION=3.13
ARG POETRY_VERSION=2.1.3

ENV PYENV_ROOT="${HOME}/.pyenv"
ENV PATH="${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:${HOME}/.local/bin:$PATH"
RUN curl https://pyenv.run | bash \
    && pyenv install ${PYTHON_VERSION} \
    && pyenv global ${PYTHON_VERSION} \
    && pip install pre-commit \
    && pip install poetry==${POETRY_VERSION}

# install ruby things
ARG RUBY_VERSION=3.4.1
ARG TRMNLP_VERSION=0.5.6

ENV RBENV_ROOT="${HOME}/.rbenv"
ENV PATH="${RBENV_ROOT}/shims:${RBENV_ROOT}/bin:$PATH"
RUN git clone https://github.com/rbenv/rbenv.git ${RBENV_ROOT} \
    && git clone https://github.com/rbenv/ruby-build.git ${RBENV_ROOT}/plugins/ruby-build \
    && echo 'eval "$(rbenv init -)"' >> ${HOME}/.bashrc \
    && mkdir -p ${RBENV_ROOT}/versions \
    && ${RBENV_ROOT}/bin/rbenv install ${RUBY_VERSION} \
    && ${RBENV_ROOT}/bin/rbenv global ${RUBY_VERSION} \
    && ${RBENV_ROOT}/bin/rbenv rehash \
    && gem update --system \
    && gem install trmnl_preview -v ${TRMNLP_VERSION} \
    && chown -R ${USER}:${USER} ${RBENV_ROOT}

USER ${USER}
