ARG VARIANT=3-bullseye
FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN \
    apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspaces

# Install Python dependencies from requirements
COPY requirements.txt requirements-dev.txt ./
COPY docs/requirements.txt ./requirements-docs.txt
RUN pip3 install -r requirements.txt \
    -r requirements-dev.txt \
    -r requirements-docs.txt \
    && rm -f requirements.txt requirements-dev.txt requirements-docs.txt

ENV PATH=/root/.local/bin:${PATH}

# Set the default shell to bash instead of sh
ENV SHELL /bin/bash
