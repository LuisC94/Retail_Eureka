
import base64
import requests

def generate_png(diagram_code, filename):
    graphbytes = diagram_code.encode("utf8")
    base64_bytes = base64.b64encode(graphbytes)
    base64_string = base64_bytes.decode("ascii")
    url = "https://mermaid.ink/img/" + base64_string
    
    print(f"Generating {filename}...")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"Success: {filename}")
        else:
            print(f"Error {response.status_code} for {filename}")
    except Exception as e:
        print(f"Exception for {filename}: {e}")

# 1. Main Architecture Diagram (No Legend)
diagram_main = """
graph TD
    %% Define Repositories OUTSIDE subgraphs
    Repo1(Repo: SAIP-ChaincodeRestApi-main)
    Repo2(Repo: SAIP-Chaincode-main)

    %% Style repos detailed text
    style Repo1 fill:#ffffff,stroke:none,color:#555,font-size:10px
    style Repo2 fill:#ffffff,stroke:none,color:#555,font-size:10px

    subgraph Container1 [Container 1: Django Web Platform]
        direction TB
        UI[Frontend HTML/JS]
        Backend[Backend Python]
        UI --> Backend
    end

    subgraph Middleware [Container 2: Middleware]
        API[Go REST API]
    end

    subgraph Fabric [Blockchain Network]
        Peer[Peer0]
        Couch[CouchDB]
        Orderer[Orderer]
        CA[CA Org1]
    end

    %% Apply YELLOW styling to Django
    style Container1 fill:#ffffcc,stroke:#333
    
    %% Apply GREEN styling to SAIP Components
    style Middleware fill:#d5f7d5,stroke:#333
    style Fabric fill:#d5f7d5,stroke:#333

    %% Main Connections
    Backend -->|JSON| API
    API -->|Signed Tx| Peer
    API -->|Order| Orderer
    Peer <--> Couch
    API -.-> CA

    %% Link Repos
    Repo1 -.-> Middleware
    Repo2 -.-> Fabric
"""

# 2. Legend Only
diagram_legend = """
graph TD
    subgraph Legend [Legend]
        direction TB
        Key1[Django Platform]
        Key2[SAIP Repositories]
    end
    
    style Key1 fill:#ffffcc,stroke:#333
    style Key2 fill:#d5f7d5,stroke:#333
    style Legend fill:#ffffff,stroke:#999,stroke-dasharray: 5 5,color:#555
"""

if __name__ == "__main__":
    generate_png(diagram_main, "full_architecture_diagram_english.png")
    generate_png(diagram_legend, "architecture_legend.png")
