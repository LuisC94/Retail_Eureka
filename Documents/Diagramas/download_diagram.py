import base64
import requests
import sys

# The Mermaid code
mermaid_code = """
erDiagram
    USER ||--|| USER_PROFILE : "tem"
    USER ||--o{ WAREHOUSE : "possui"

    PRODUCT ||--o{ PRODUCT_SUBFAMILY : "tem variantes"

    USER ||--o{ PLANTATION_PLAN : "gere"
    PLANTATION_PLAN ||--o{ PLANTATION_CROP : "cultiva detalhes"
    PLANTATION_PLAN ||--o{ PLANTATION_SOIL_VALUE : "tem analises solo"
    PLANTATION_PLAN ||--o{ PLANTATION_EVENT : "regista operacoes"
    PLANTATION_PLAN ||--o{ HARVEST : "gera colheitas"
    
    PLANTATION_EVENT |o--o| FERTILIZER_DATA : "detalha fertilizacao"
    PLANTATION_EVENT |o--o| PEST_CONTROL_DATA : "detalha fitofarmacos"
    PLANTATION_EVENT |o--o| IRRIGATION_DATA : "detalha rega"

    HARVEST }o--o| WAREHOUSE : "armazenado em"
    USER ||--o{ MARKETPLACE_ORDER : "cria pedido"
    MARKETPLACE_ORDER }o--|| PRODUCT_SUBFAMILY : "transaciona"
    MARKETPLACE_ORDER |o--o| HARVEST : "origina de (Venda)"
    
    BLOCKCHAIN_BLOCK {
        int block_index
        string batch_id
        string previous_hash
        string current_hash
        json data_content
        string event_type
    }
"""

def generate_image():
    # Basic cleanup
    graph = mermaid_code.strip()
    
    # Encode to base64
    graphbytes = graph.encode("ascii")
    base64_bytes = base64.b64encode(graphbytes)
    base64_string = base64_bytes.decode("ascii")
    
    # Construct URL
    url = "https://mermaid.ink/img/" + base64_string
    
    print(f"Downloading fro URL length: {len(url)}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        with open("schema_diagram.png", "wb") as f:
            f.write(response.content)
        print("Successfully saved schema_diagram.png")
        
    except Exception as e:
        print(f"Error downloading image: {e}")
        # Fallback explanation or empty file handling
        sys.exit(1)

if __name__ == "__main__":
    generate_image()
