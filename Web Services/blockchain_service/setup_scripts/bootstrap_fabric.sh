#!/usr/bin/env bash
# ==============================================================================
# Script de Instalação e Bootstrap do Hyperledger Fabric (LTS 2.5.x)
# Executar num ambiente Linux / WSL2 (Ubuntu)
# ==============================================================================

set -e

echo "=================================================================="
echo "  RETAIL EUREKA - INSTALAÇÃO DO HYPERLEDGER FABRIC (LOCAL)        "
echo "=================================================================="

# 1. Verificar Pré-requisitos
echo "[1/4] A verificar pré-requisitos (Docker, Git, cURL, jq)..."
command -v docker >/dev/null 2>&1 || { echo >&2 "[ERRO] Docker não está instalado ou ativo. Instale/inicie o Docker Desktop antes de continuar."; exit 1; }
command -v git >/dev/null 2>&1 || { echo >&2 "[ERRO] Git não está instalado."; exit 1; }
command -v curl >/dev/null 2>&1 || { echo >&2 "[ERRO] cURL não está instalado."; exit 1; }
command -v jq >/dev/null 2>&1 || { echo >&2 "[ERRO] jq não está instalado. Execute: sudo apt-get update && sudo apt-get install -y jq"; exit 1; }

echo "[OK] Pré-requisitos do sistema validados com sucesso."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${TARGET_DIR}"

# 2. Descarregar fabric-samples se não existir
if [ ! -d "fabric-samples/test-network" ]; then
    echo "[2/4] A clonar o repositório fabric-samples..."
    rm -rf fabric-samples
    git clone https://github.com/hyperledger/fabric-samples.git
else
    echo "[2/4] A pasta 'fabric-samples' já existe e está pronta."
fi

# 3. Descarregar os binários oficiais e imagens Docker do Hyperledger Fabric se necessário
if [ ! -d "bin" ] || [ ! -f "bin/peer" ]; then
    echo "[3/4] A descarregar binários do Fabric v2.5.4 e imagens Docker..."
    curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/install-fabric.sh | bash -s -- binary docker
fi

# Garantir que os binários e configs estão presentes em fabric-samples/ para o network.sh
mkdir -p "${TARGET_DIR}/fabric-samples/bin"
mkdir -p "${TARGET_DIR}/fabric-samples/config"
cp -r "${TARGET_DIR}/bin/"* "${TARGET_DIR}/fabric-samples/bin/" 2>/dev/null || true
cp -r "${TARGET_DIR}/config/"* "${TARGET_DIR}/fabric-samples/config/" 2>/dev/null || true

# Exportar PATH para validação
export PATH="${TARGET_DIR}/bin:${TARGET_DIR}/fabric-samples/bin:$PATH"
export FABRIC_CFG_PATH="${TARGET_DIR}/config"

echo "Validando binário peer:"
peer version || true

# 4. Instalar dependências do Chaincode (Node.js)
echo "[4/4] A instalar dependências do Chaincode (npm install)..."
cd "${TARGET_DIR}/chaincode"
if command -v npm >/dev/null 2>&1; then
    npm install --silent
else
    echo "[AVISO] npm não encontrado localmente. As dependências serão geridas pelo Docker no deployCC."
fi

echo "=================================================================="
echo "  [SUCESSO] Bootstrap concluído com sucesso!                      "
echo "  Para iniciar a rede e fazer o deploy do chaincode execute:      "
echo "  ./setup_scripts/start_network_and_deploy.sh                     "
echo "=================================================================="
