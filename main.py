import base64
from datetime import datetime
import json
import os
import time
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
load_dotenv()
from datetime import datetime, timezone, timedelta

# Fuso horário fixo de Brasília (UTC-3)
TZ_BRASILIA = timezone(timedelta(hours=-3))



# ================= CONFIGURAÇÕES =================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = "llPancho/api-ceee"
CAMINHO_NO_REPO = "dados/dados_ceee.json"
BRANCH = "main"
INTERVALO_SEGUNDOS = 15 * 60  # 15 minutos
# =================================================

def agora_brasilia(formato="%Y-%m-%d %H:%M:%S") -> str:
    """Retorna o timestamp atual formatado no horário de Brasília."""
    return datetime.now(TZ_BRASILIA).strftime(formato)


def salvar_ou_substituir_no_github(dados):
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN não encontrado nas variáveis de ambiente / .env")

    url = f"https://api.github.com/repos/{REPO}/contents/{CAMINHO_NO_REPO}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    # 1. Verifica se o arquivo já existe para obter seu SHA e conteúdo atual
    res_get = requests.get(url, headers=headers, params={"ref": BRANCH})
    sha = None
    conteudo_novo_json = json.dumps(dados, indent=2, ensure_ascii=False)
    
    if res_get.status_code == 200:
        info_arquivo = res_get.json()
        sha = info_arquivo.get("sha")
        
        # Evita commit desnecessário se o conteúdo for idêntico
        conteudo_antigo = base64.b64decode(info_arquivo.get("content", "")).decode("utf-8")
        if conteudo_antigo.strip() == conteudo_novo_json.strip():
            print("ℹ️ Dados idênticos aos anteriores. Nenhum commit necessário.")
            return

    elif res_get.status_code != 404:
        print(f"⚠️ Aviso ao consultar repositório ({res_get.status_code}): {res_get.text}")

    # 2. Converte para Base64
    conteudo_base64 = base64.b64encode(conteudo_novo_json.encode("utf-8")).decode("utf-8")

    # 3. Monta o payload do commit com timestamp no horário de Brasília
    agora = agora_brasilia("%Y-%m-%d %H:%M:%S")
    payload = {
        "message": f"Atualização automática CEEE - {agora}",
        "content": conteudo_base64,
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha

    # 4. Envia o commit via PUT
    res_put = requests.put(url, headers=headers, json=payload)
    if res_put.status_code in [200, 201]:
        print(f" Sucesso! Commit realizado às {agora} (Horário de Brasília).")
    else:
        print(f"❌ Erro ao commitar no GitHub ({res_put.status_code}): {res_put.text}")


def extrair_dados_ceee():
    print(f"\n[{agora_brasilia('%H:%M:%S')}] Iniciando captura...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context = browser.new_context(
            no_viewport=True,
            locale="pt-BR",
            timezone_id="America/Sao_Paulo"  # Define também o fuso no navegador do Playwright
        )

        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """)

        with page.expect_response(
            lambda res: "api-etr/resumo" in res.url and res.status == 200,
            timeout=45000
        ) as response_info:
            page.goto(
                "https://ceee.equatorialenergia.com.br/monitoramento-de-interrupcoes/",
                wait_until="networkidle"
            )

        response = response_info.value
        dados = response.json()
        browser.close()
        return dados


def main():
    print(" Início do monitoramento CEEE (intervalo: 15 minutos)...")
    while True:
        try:
            dados = extrair_dados_ceee()
            salvar_ou_substituir_no_github(dados)
        except Exception as e:
            print(f"❌ Ocorreu um erro no ciclo atual: {e}")
        
        print(" Aguardando 15 minutos para a próxima checagem...")
        time.sleep(INTERVALO_SEGUNDOS)


if __name__ == "__main__":
    main()