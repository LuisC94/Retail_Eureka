# Estratégia de Migração para Blockchain Real (Hyperledger Fabric)

Este documento oficializa a decisão de abandonar a simulação de blockchain atual e passar para uma implementação real baseada na tecnologia Hyperledger Fabric (projeto "TrabalhoTurcos"), com adaptações específicas para o nosso caso de uso.

## 1. Fim da Simulação (O que vai desaparecer)

Atualmente, o projeto `Retail-Eureka` tem uma aplicação Django chamada `blockchain` que simula uma cadeia de blocos usando uma tabela PostgreSQL (`BlockchainBlock`).

**Decisão:**
*   Vamos deixar de usar o `blockchain/services.py` para criar blocos.
*   Vamos deixar de guardar hashes na tabela SQL `BlockchainBlock`.
*   A "verdade" sobre a rastreabilidade passará a residir exclusivamente na rede Hyperledger Fabric.

## 2. Integração do Código "TrabalhoTurcos" (A Nova Arquitetura)

Vamos adotar o código da pasta `TrabalhoTurcos` para criar uma infraestrutura real:

*   **Rede Blockchain:** Usaremos os scripts e binários do Hyperledger Fabric para levantar uma rede local (Peers, Orderers) dentro do WSL (Linux).
*   **Smart Contract (Chaincode):** Usaremos o código Node.js (`SAIP-Chaincode-main`) para definir as regras de negócio.
*   **Middleware (Ponte):** Usaremos a API em Go (`SAIP-ChaincodeRestApi-main`) para permitir que o nosso Django comunique com a Blockchain via HTTP.

**Fluxo de Dados:**
`Django (Windows)` -> `HTTP POST` -> `Go API (WSL)` -> `gRPC` -> `Hyperledger Network (Docker)`

## 3. Adaptações e Simplificações (O Nosso "Fork")

Ao analisarmos o código original turco, identificámos regras de negócio que não se aplicam ao nosso projeto (ex: obrigatoriedade de matrícula de camião). Fizemos as seguintes alterações críticas ao código original:

### A. Remoção da Lógica "Kargolandi"
O código original exigia que o estado fosse "Kargolandi" para aceitar certas atualizações.
*   **Alteração:** Removemos esta verificação. O Smart Contract agora aceita atualizações de estado genéricas.
*   **Novo Termo:** Usaremos `IN_TRANSIT` para representar o transporte, em vez de termos turcos.

### B. Remoção do Campo 'Matrícula' (trackingNo)
A nossa interface de Transportador (no botão "Pickup") não pede a matrícula do veículo, apenas confirma a recolha.
*   **Alteração:** Alterámos a função `UpdateOrderStatus` no `chaincode.js` para deixar de exigir ou processar o campo `trackingNo`.
*   **Resultado:** A função tornou-se mais leve e genérica: `UpdateOrderStatus(ctx, id, orderStatus, orderProductId, status, proccessDate)`.

---

**Próximo Passo:** Implementar o serviço `FabricService` no Django para começar a enviar estes dados para a nova API.
