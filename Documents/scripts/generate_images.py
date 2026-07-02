import os
from playwright.sync_api import sync_playwright

with open('db_diagram_utf8.mermaid', 'r', encoding='utf-8') as f:
    mermaid_text = f.read()

html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Database ER Diagram</title>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'default',
            securityLevel: 'loose',
            fontFamily: 'arial'
        }});
    </script>
    <style>
        body {{
            background: white;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
        }}
        .mermaid {{
            background: white;
        }}
    </style>
</head>
<body>
    <div class="mermaid" id="diagram">
{mermaid_text}
    </div>
</body>
</html>
"""

html_path = os.path.abspath('temp_diagram.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Load local HTML
        page.goto(f'file:///{html_path}')
        
        # Wait for mermaid to render (SVG will be added inside #diagram)
        page.wait_for_selector('#diagram svg', state='attached', timeout=30000)
        
        # Small delay to ensure styles and fonts are applied
        page.wait_for_timeout(2000)
        
        # 1. Save PNG
        element = page.locator('#diagram')
        element.screenshot(path="Diagrama_Estrutura_BaseDados.png", omit_background=False)
        
        # 2. Save PDF
        # We need to set the page size to match the element
        box = element.bounding_box()
        page.pdf(
            path="Diagrama_Estrutura_BaseDados.pdf",
            width=f"{box['width'] + 40}px",
            height=f"{box['height'] + 40}px",
            print_background=True,
            page_ranges="1"
        )
        
        # 3. Save SVG (vectorial)
        svg_content = page.locator('#diagram').inner_html()
        with open('Diagrama_Estrutura_BaseDados.svg', 'w', encoding='utf-8') as f:
            f.write(svg_content)
            
        browser.close()

if __name__ == '__main__':
    run()
    if os.path.exists(html_path):
        os.remove(html_path)
    print("Arquivos gerados com sucesso: PNG, PDF e SVG.")
