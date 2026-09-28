import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
JSON_PATH = Path(__file__).parent / "dados_ceee.json"
INTERVALO_MINUTOS = 15
CEEE_URL = "https://ceee.equatorialenergia.com.br/monitoramento-de-interrupcoes/"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Estado global compartilhado
estado = {
    "ultima_atualizacao": None,
    "proxima_atualizacao": None,
    "atualizando": False,
    "erro": None,
}


# ---------------------------------------------------------------------------
# Scraper (Playwright headless)
# ---------------------------------------------------------------------------

def _executar_scraper() -> dict:
    """Executa exatamente a mesma lógica e configuração do main.py."""
    from playwright.sync_api import sync_playwright

    log.info("Iniciando scraper Playwright (exato ao main.py)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )

        context = browser.new_context(
            no_viewport=True,
            locale="pt-BR",
        )

        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        with page.expect_response(
            lambda res: "api-etr/resumo" in res.url and res.status == 200,
            timeout=30000,
        ) as response_info:
            page.goto(
                CEEE_URL,
                wait_until="networkidle",
            )

        response = response_info.value
        dados = response.json()
        browser.close()

    log.info("Scraper concluído com sucesso.")
    return dados

async def _atualizar_dados():
    """Executa o scraper em thread separada e salva o JSON."""
    if estado["atualizando"]:
        log.warning("Atualizacao ja em andamento, ignorando.")
        return

    estado["atualizando"] = True
    estado["erro"] = None

    try:
        # Roda o Playwright (sincrono) em thread separada para nao bloquear o event loop
        dados = await asyncio.get_event_loop().run_in_executor(None, _executar_scraper)

        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)

        agora = datetime.now(timezone.utc)
        estado["ultima_atualizacao"] = agora.isoformat()
        log.info("JSON atualizado em %s", estado["ultima_atualizacao"])

    except Exception as exc:
        estado["erro"] = str(exc)
        log.error("Erro ao atualizar dados: %s", exc)

    finally:
        estado["atualizando"] = False


async def _loop_atualizacao():
    """Loop que atualiza os dados a cada INTERVALO_MINUTOS."""
    # Roda imediatamente ao iniciar
    await _atualizar_dados()

    while True:
        await asyncio.sleep(INTERVALO_MINUTOS * 60)
        await _atualizar_dados()


# ---------------------------------------------------------------------------
# Ciclo de vida FastAPI
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    tarefa = asyncio.create_task(_loop_atualizacao())
    log.info("Agendador iniciado - atualizacao a cada %d minutos.", INTERVALO_MINUTOS)
    yield
    tarefa.cancel()
    try:
        await tarefa
    except asyncio.CancelledError:
        pass
    log.info("Agendador encerrado.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="API CEEE - Monitoramento de Interrupcoes",
    description="Serve os dados do monitoramento de interrupcoes da CEEE/Equatorial, atualizados automaticamente a cada 15 minutos.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@app.get("/", summary="Raiz")
async def raiz():
    return {
        "api": "CEEE Monitoramento de Interrupcoes",
        "endpoints": ["/dados", "/status", "/atualizar"],
    }


@app.get("/dados", summary="Retorna os dados do JSON salvo")
async def get_dados():
    if not JSON_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Dados ainda nao disponiveis. Aguarde a primeira coleta.",
        )

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        dados = json.load(f)

    return JSONResponse(content=dados)


@app.get("/status", summary="Status da ultima atualizacao")
async def get_status():
    json_existe = JSON_PATH.exists()
    tamanho = JSON_PATH.stat().st_size if json_existe else 0

    return {
        "ultima_atualizacao": estado["ultima_atualizacao"],
        "atualizando_agora": estado["atualizando"],
        "erro_ultimo": estado["erro"],
        "json_existe": json_existe,
        "json_tamanho_bytes": tamanho,
        "intervalo_minutos": INTERVALO_MINUTOS,
    }


@app.post("/atualizar", summary="Forca uma atualizacao imediata dos dados")
async def forcar_atualizacao():
    if estado["atualizando"]:
        return {"mensagem": "Ja existe uma atualizacao em andamento."}

    asyncio.create_task(_atualizar_dados())
    return {"mensagem": "Atualizacao iniciada em background."}
