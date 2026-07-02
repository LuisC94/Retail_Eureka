import base64
import requests
import sys

# The Mermaid code from architecture_design.md
mermaid_code = """
%%{init: {'flowchart': {'nodeSpacing': 100, 'rankSpacing': 100}}}%%
graph TD
    subgraph DockerHost ["<b>Docker Host</b>"]
        direction TB
        
        UI[Utilizador] -->|HTTP| Django[Django Core / Web]
        
        subgraph Infraestrutura
            DB[(PostgreSQL)]
        end

        subgraph IntegratedAgents ["Integrated Agents Context"]
            Django -->|Internal Import| StockAgent[Ger. Stock]
            Django -->|Internal Import| OrderAgent[Ger. Pedidos]
            Django -->|Internal Import| MCDA[Multicriteria Decision Agent]
        end

        subgraph IndependentAgents ["Independent Agents"]
            Tracking[Agente Tracking]
            LCA[Agente LCA]
            LC[Agente LC Model]
            Crit[Agente Eventos Críticos]
        end

        %% Comunicação Síncrona (Dados para UI)
        Django -- REST API (JSON) --> LCA
        Django -- REST API (JSON) --> LC

        %% Comunicação Assíncrona (Eventos)
        Crit -- 3. Notify/Action --> Django
        
        %% Acesso a Dados
        Django -.-> DB
        Tracking -.-> DB
        LCA -.-> DB
    end
"""

def generate_image():
    # Basic cleanup
    graph = mermaid_code.strip()
    
    # Encode to base64
    graphbytes = graph.encode("utf-8")
    base64_bytes = base64.b64encode(graphbytes)
    base64_string = base64_bytes.decode("ascii")
    
    # Construct URL
    url = "https://mermaid.ink/img/" + base64_string
    
    print(f"Downloading fro URL length: {len(url)}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        filename = "architecture_connection_diagram.png"
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"Successfully saved {filename}")
        
    except Exception as e:
        print(f"Error downloading image: {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_image()
