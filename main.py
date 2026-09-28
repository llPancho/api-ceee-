import json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        channel="chrome",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--start-maximized"
        ]
    )

    context = browser.new_context(
        no_viewport=True,
        locale="pt-BR"
    )

    page = context.new_page()

    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    # Configura para capturar a resposta quando a URL da API for chamada
    with page.expect_response(
        lambda res: "api-etr/resumo" in res.url and res.status == 200,
        timeout=30000
    ) as response_info:
        # Apenas abre o painel principal; ele próprio fará o fetch dos dados
        page.goto(
            "https://ceee.equatorialenergia.com.br/monitoramento-de-interrupcoes/",
            wait_until="networkidle"
        )

    response = response_info.value
    dados = response.json()

    print(json.dumps(dados, indent=2, ensure_ascii=False))

    with open("dados_ceee.json", "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
        print("Arquivo salvo com sucesso!")

    browser.close()