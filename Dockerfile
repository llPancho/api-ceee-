FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instala ferramentas do sistema, Xvfb e bibliotecas gráficas
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    xvfb \
    ca-certificates \
    curl \
    fonts-liberation \
    libasound2 \
    libnss3 \
    libxss1 \
    && rm -rf /var/lib/apt/lists/*

# Instala o Google Chrome oficial (necessário para channel="chrome")
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pega o executável do uv diretamente da imagem oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copia os arquivos de dependência do uv
COPY pyproject.toml uv.lock ./

# Sincroniza e instala todas as dependências no Python do sistema
RUN uv pip install --system -r pyproject.toml

# Instala dependências de SO exigidas pelo Playwright
RUN playwright install-deps

COPY . .

EXPOSE 8000

# Executa o Uvicorn sob o display virtual Xvfb
CMD ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1920x1080x24", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]