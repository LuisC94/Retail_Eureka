# Retail Eureka - Blockchain Web Service (Hyperledger Fabric)

Microserviço autónomo de Rastreabilidade e Imutabilidade na Cadeia de Abastecimento baseado em **Hyperledger Fabric (v2.5.x LTS)** e **API REST em Golang** (Porta `3000`).

---

## 🏗️ Estrutura do Pacote

```
blockchain_service/
├── chaincode/                     # Smart Contract em Node.js (saip / chaincode.js)
│   ├── lib/chaincode.js           # Funções: CreateOrder, ReadOrder, UpdateOrder, GetAllOrders
│   └── package.json
├── rest_api/                      # Web Service REST Middleware em Go (Porta 3000)
│   ├── main.go                    # Configuração dos certificados MSP e ligação gRPC ao Peer
│   ├── go.mod & go.sum
│   └── web/ (app.go, invoke.go, query.go)
├── setup_scripts/                 # Scripts de automação para ambiente Linux / WSL2
│   ├── bootstrap_fabric.sh        # Descarrega binários e imagens Docker oficiais do Fabric
│   ├── start_network_and_deploy.sh# Sobe a rede, cria 'mychannel' e instala o chaincode 'saip'
│   └── stop_network.sh            # Pára os contentores e limpa o ambiente
├── test_client.py                 # Script de validação dos endpoints /invoke e /query
├── README.md                      # Este documento
└── Manual_Instalacao_Deploy_Blockchain.docx # 📄 MANUAL COMPLETO PASSO A PASSO
```

---

## 🚀 Como Instalar e Iniciar a Rede Localmente (Passo a Passo)

### 1. Pré-requisitos
Certifique-se de que tem instalado no seu sistema (Linux nativo ou Windows com WSL2 Ubuntu):
- **Docker & Docker Compose** (em execução)
- **Go (Golang)**: versão 1.20 ou superior
- **Node.js & npm**: versão 18 ou superior
- **Git** e **cURL**

---

### 2. Descarregar o Hyperledger Fabric (Bootstrap)
Dentro da pasta `blockchain_service`, execute:
```bash
chmod +x setup_scripts/*.sh
./setup_scripts/bootstrap_fabric.sh
```
*Este comando descarrega as imagens Docker oficiais do Hyperledger Fabric e os utilitários de linha de comando (`peer`, `configtxgen`) para a pasta `fabric-samples/`.*

---

### 3. Levantar a Rede e Instalar o Smart Contract (Chaincode)
Execute o script de automação:
```bash
./setup_scripts/start_network_and_deploy.sh
```
*Este script:*
1. Cria a rede com Certificate Authority (`-ca`), nós *Orderer* e *Peers*.
2. Cria o canal de comunicação `mychannel`.
3. Empacota, aprova e faz o *commit* do contrato inteligente `saip` (localizado em `chaincode/`).

---

### 4. Iniciar o Web Service REST em Go (Porta 3000)
Num terminal (na pasta `rest_api`):
```bash
cd rest_api
go run main.go
```
A API estará em execução em: **`http://localhost:3000`**

---

## 📡 Endpoints do Web Service

### 1. Gravar / Modificar Dados (`POST /invoke`)
- **URL:** `http://localhost:3000/invoke`
- **Form Data (Content-Type: `application/x-www-form-urlencoded`):**
  - `channelid`: `mychannel`
  - `chaincodeid`: `saip`
  - `function`: `CreateOrder` (ou `UpdateOrder`)
  - `args`: `[JSON com os dados do lote]`

### 2. Consultar Dados (`POST /query`)
- **URL:** `http://localhost:3000/query`
- **Form Data:**
  - `channelid`: `mychannel`
  - `chaincodeid`: `saip`
  - `function`: `ReadOrder` (ou `GetAllOrders`)
  - `args`: `["ID_DO_LOTE"]`

---

## 🧪 Como Testar o Web Service
Para testar a gravação e consulta automática de um lote de teste, execute:
```bash
python test_client.py
```

---

## 🔗 Ligação à Plataforma Django
No ficheiro `.env` ou `core/settings.py` da plataforma Django, configure:
```ini
FABRIC_API_URL=http://localhost:3000
```
O Django comunicará automaticamente com o Web Service através do módulo `dashboard/services/fabric_service.py` (`FabricService`).
