
import base64
import requests

# Simplified diagram for reliability
diagram = """
graph TD
    subgraph Container1 [Plataforma Web Django]
        UI[Frontend HTML/JS]
        Backend[Backend Python]
    end

    subgraph Container2 [Middleware]
        API[API Go Chaincode]
    end

    subgraph Container3 [Rede Blockchain]
        Peer[Peer0]
        Couch[CouchDB]
        Orderer[Orderer]
        CA[CA Org1]
    end

    UI --> Backend
    Backend -->|JSON| API
    API -->|Signed Trans| Peer
    API -->|Order| Orderer
    Peer <--> Couch
    API -.-> CA
"""

graphbytes = diagram.encode("ascii")
base64_bytes = base64.b64encode(graphbytes)
base64_string = base64_bytes.decode("ascii")

url = "https://mermaid.ink/img/" + base64_string

response = requests.get(url)

if response.status_code == 200:
    with open("full_architecture_diagram.png", "wb") as f:
        f.write(response.content)
    print("PNG generated successfully: full_architecture_diagram.png")
else:
    print(f"Error generating PNG: {response.status_code}")
