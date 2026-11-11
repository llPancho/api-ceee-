# 1. Imagem base oficial do Playwright com Python sobre Ubuntu
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

# 2. Copia os binários do uv direto da imagem oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 3. Variáveis de ambiente essenciais
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1

WORKDIR /app

# 4. Instala Xvfb, utilitários de processo e dependências de execução
RUN (apt-get update --fix-missing || apt-get update) && apt-get install -y --no-install-recommends \
    xvfb \
    psmisc \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 5. Copia e instala as dependências Python usando o uv
COPY requirements.txt .
RUN uv pip install -r requirements.txt

# 6. Garante o binário do Chromium do Playwright
RUN playwright install chromium

# 7. Copia todo o código da aplicação
COPY . .

# 8. Executa via xvfb-run:
# - -a: aloca automaticamente um display livre (evita conflito com :99 e locks residuais)
# - --server-args: desativa controle de acesso (-ac) e suprime logs do servidor X (2>/dev/null)
CMD ["bash", "-c", "xvfb-run -a --server-args='-screen 0 1920x1080x24 -ac' python -u main.py 2> >(grep -v -E 'xkbcomp|XF86|Could not resolve keysym' >&2)"]