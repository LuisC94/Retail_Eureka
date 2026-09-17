#!/usr/bin/env bash
# ==============================================================================
# Script de Paragem e Limpeza da Rede Blockchain
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEST_NET_DIR="${BASE_DIR}/fabric-samples/test-network"

if [ -d "${TEST_NET_DIR}" ]; then
    cd "${TEST_NET_DIR}"
    echo "[Blockchain Service] A parar os contentores Docker da rede Hyperledger Fabric..."
    ./network.sh down || true
    docker rm -f $(docker ps -aq) 2>/dev/null || true
    docker volume rm $(docker volume ls -q) 2>/dev/null || true
    rm -rf channel-artifacts organizations/peerOrganizations organizations/ordererOrganizations
    echo "[OK] Rede parada e recursos limpos com sucesso."
else
    echo "[AVISO] Diretoria 'fabric-samples/test-network' não encontrada."
fi
