
import base64
import requests

# Re-applying logic with GREEN styling and a LEGEND
diagram = """
graph TD
    %% Define Repositories OUTSIDE subgraphs
    Repo1(Repo: SAIP-ChaincodeRestApi-main)
    Repo2(Repo: SAIP-Chaincode-main)

    %% Style them to look like plain text (white fill, no border)
    style Repo1 fill:#ffffff,stroke:none,color:#555
    style Repo2 fill:#ffffff,stroke:none,color:#555

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

    %% Apply GREEN styling to the Blockchain components
    style Middleware fill:#d5f7d5,stroke:#333
    style Fabric fill:#d5f7d5,stroke:#333

    %% Main Connections
    Backend -->|JSON| API
    API -->|Signed Tx| Peer
    API -->|Order| Orderer
    Peer <--> Couch
    API -.-> CA

    %% Link Repos to Containers (Dashed lines, outside boxes)
    Repo1 -.-> Middleware
    Repo2 -.-> Fabric

    %% LEGEND (Using a subgraph to group legend items)
    subgraph Legend [Legend]
        L1[Web Platform Area]
        L2[Blockchain Components Area]
    end
    
    style L2 fill:#d5f7d5,stroke:#333
    style Legend fill:#ffffff,stroke:#999,stroke-dasharray: 5 5
"""

graphbytes = diagram.encode("utf8")
base64_bytes = base64.b64encode(graphbytes)
base64_string = base64_bytes.decode("ascii")

# Using .png URL to force image generation
url = "https://mermaid.ink/img/" + base64_string

response = requests.get(url)

if response.status_code == 200:
    with open("full_architecture_diagram_english.png", "wb") as f:
        f.write(response.content)
    print("PNG generated successfully.")
else:
    print(f"Error generating PNG: {response.status_code}")
