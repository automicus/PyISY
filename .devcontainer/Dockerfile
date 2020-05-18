FROM python:3.8

RUN \
    apt-get update && apt-get install -y --no-install-recommends \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspaces

# Install Python dependencies from requirements
COPY requirements.txt requirements-dev.txt ./
RUN pip3 install -r requirements.txt \
    && pip3 install -r requirements-dev.txt \
    && rm -f requirements.txt requirements-dev.txt

ENV PATH=/root/.local/bin:${PATH}

# Set the default shell to bash instead of sh
ENV SHELL /bin/bash
