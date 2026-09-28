# 1. Imagem base oficial do Playwright com Python sobre Ubuntu
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

# 2. Copia os binários do uv direto da imagem oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 3. Variáveis de ambiente essenciais
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1
ENV DISPLAY=:99

WORKDIR /app

# 4. Instala o Xvfb e procps (para killall/ps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    psmisc \
    && rm -rf /var/lib/apt/lists/*

# 5. Copia e instala as dependências Python usando o UV
COPY requirements.txt .
RUN uv pip install -r requirements.txt

# 6. Garante que os navegadores do Playwright estejam prontos
RUN playwright install chromium

# 7. Copia o código da aplicação
COPY . .

# 8. Inicia o Xvfb com controle de acesso desativado (-ac) e roda o Python
CMD ["sh", "-c", "Xvfb :99 -screen 0 1920x1080x24 -ac & sleep 1 && python -u main.py"]