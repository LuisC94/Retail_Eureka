#!/usr/bin/env bash
# ==============================================================================
# Script de Arranque da Rede e Deploy Automático do Chaincode 'saip'
# Executar num ambiente Linux / WSL2 (Ubuntu)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEST_NET_DIR="${BASE_DIR}/fabric-samples/test-network"
CHAINCODE_DIR="${BASE_DIR}/chaincode"

echo "=================================================================="
echo "  RETAIL EUREKA - ARRANQUE DA REDE BLOCKCHAIN & DEPLOY CHAINCODE "
echo "=================================================================="

if [ ! -d "${TEST_NET_DIR}" ]; then
    echo "[ERRO] Pasta 'fabric-samples/test-network' não encontrada!"
    echo "Execute primeiro o script ./setup_scripts/bootstrap_fabric.sh"
    exit 1
fi

# Exportar caminhos dos binários e configurações do Fabric
export PATH="${BASE_DIR}/bin:${BASE_DIR}/fabric-samples/bin:$PATH"
export FABRIC_CFG_PATH="${BASE_DIR}/fabric-samples/config"

cd "${TEST_NET_DIR}"

# 1. Limpar eventuais contentores e volumes anteriores
echo "[1/4] A limpar instâncias e volumes residuais da rede..."
./network.sh down || true
docker rm -f $(docker ps -aq) 2>/dev/null || true
docker volume rm $(docker volume ls -q) 2>/dev/null || true
rm -rf channel-artifacts organizations/peerOrganizations organizations/ordererOrganizations

# 2. Levantar os nós da rede com Certificate Authority (CA) e criar o canal 'mychannel'
echo "[2/4] A levantar nós (Peers, Orderer, CA) e a criar canal 'mychannel'..."
./network.sh up createChannel -c mychannel -ca

# 3. Fazer o Deploy do Smart Contract (Chaincode em JavaScript)
echo "[3/4] A fazer o deploy do Chaincode 'saip' no canal 'mychannel'..."
./network.sh deployCC -ccn saip -ccp "${CHAINCODE_DIR}" -ccl javascript

echo "[4/4] A verificar contentores Docker em execução..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo "=================================================================="
echo "  [SUCESSO] Rede Blockchain ativa e Chaincode 'saip' em execução! "
echo "  Para iniciar o Web Service REST em Go:                          "
echo "  cd rest_api && go run main.go                                   "
echo "=================================================================="
