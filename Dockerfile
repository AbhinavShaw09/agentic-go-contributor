FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    golang-go \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://opencode.ai/install | bash -s -- --no-modify-path
ENV PATH="/root/.opencode/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml .
RUN pip install poetry && poetry install --no-root

COPY . .

ENTRYPOINT ["poetry", "run", "python", "-m", "agentic_go_contributor.cli"]
