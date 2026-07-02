# A Viagem de uma Maçã: Fluxo Completo dos Dados

Este documento explica passo-a-passo como o teu software funciona, desde o clique no botão "Encomendar" até à gravação imutável na Blockchain.

---

## O Cenário
O **Produtor João** faz login no site e regista uma nova colheita de maçãs (ou aceita uma encomenda).
O que acontece "debaixo do capô" em 6 segundos?

### Passo 1: O Clique no Frontend (Angular)
**Ficheiro:** `SAIP-Front-main/.../order-management.service.ts`

Quando o João clica em "Salvar", o site prepara um pacote de dados (JSON) e envia para o teu servidor backend.
*   **Ação:** O browser faz um pedido `HTTP POST`.
*   **Destino:** `https://teu-backend-api/api/Order/Save`

```typescript
// O site diz: "Toma lá estes dados e guarda-os!"
save(data: OrderModel) {
    return this.http.post(`${API_ORDER_URL}/Save`, data);
}
```

---

### Passo 2: O Backend Recebe e Guarda na BD Clássica (.NET)
**Ficheiro:** `SAIP-Back-main/.../Services/OrderService.cs`

O teu servidor .NET recebe o pedido. Antes de ir para a Blockchain, ele guarda tudo na base de dados normal (PostgreSQL) para o site ser rápido e ter histórico local.

1.  **Guarda no PostgreSQL:**
    ```csharp
    _dbContext.Add(order);
    await _dbContext.SaveChangesAsync(); // Gravado na tabela 'Orders'
    ```
2.  **Prepara para a Blockchain:**
    O código converte a encomenda para o formato que a Blockchain gosta (`Model.Fabric.Order`).
3.  **Chama a Blockchain:**
    ```csharp
    await _fabricService.InvokeCreateOrder(fabricOrder);
    ```

---

### Passo 3: A Ponte para a Blockchain (.NET -> Go)
**Ficheiro:** `SAIP-Back-main/.../Services/FabricService.cs`

Aqui acontece a magia da integração. O .NET não sabe falar a linguagem da Blockchain (gRPC), então ele chama o teu "Tradutor" (a API em Go).

*   **Ação:** Envia um pedido `HTTP POST` interno.
*   **Destino:** `http://localhost:3000/invoke` (Onde o Go está a ouvir).
*   **Dados:** Diz "Executa a função `CreateOrder` com estes dados...".

---

### Passo 4: O Tradutor Assina a Transação (Go)
**Ficheiros:** `SAIP-ChaincodeRestApi-main/web/app.go` & `invoke.go`

O servidor Go recebe o pedido. Ele tem a "Chave Mestra" (`User1@org1.example.com`).

1.  **Autenticação:** Usa o certificado digital do 'User1' para provar que tem permissão.
2.  **Proposta:** Cria uma transação oficial e assina-a criptograficamente.
3.  **Envio:** Envia a transação assinada para a rede Hyperledger Fabric (para os Peers).

```go
// O Go diz à rede: "Eu, User1, em nome desta app, quero executar CreateOrder"
contract.SubmitTransaction("CreateOrder", args...)
```

---

### Passo 5: A Blockchain Valida e Grava (Smart Contract)
**Ficheiro:** `SAIP-Chaincode-main/lib/chaincode.js`

Dentro da rede Docker, o código inteligente (Smart Contract) acorda.

1.  **Validação:** Verifica se a encomenda já existe (para evitar duplicados).
2.  **Gravação:** Escreve no "Livro de Registos" (World State).

```javascript
// O Regra final:
async CreateOrder(ctx, orderJSON) {
    // ... validações ...
    await ctx.stub.putState(order.id, ...); // GRAVADO PARA SEMPRE!
}
```

---

## Resumo Visual

| # | Camada | Tecnologia | O que faz? |
|---|---|---|---|
| **1** | **Frontend** | Angular | Coleta os dados do utilizador. |
| **2** | **Backend** | .NET (C#) | Guarda na BD SQL e gere a lógica de negócio. |
| **3** | **Bridge** | .NET Service | Envia os dados para a API de Blockchain. |
| **4** | **Middleware** | Go (Golang) | Assina a transação com certificados digitais. |
| **5** | **Ledger** | Hyperledger | Valida e torna o dado imutável e distribuído. |

## O Que Tens de Fazer?
Como podes ver, o fluxo já está todo programado! Não precisas de escrever código novo de integração.
Só precisas de:
1.  **Levantar a Infraestrutura** (Passo 5) - *Já estamos a fazer isto.*
2.  **Ligar o Middleware** (Passo 4) - *Correr o `main.go`.*
3.  **Configurar o Backend** (Passo 3) - *Apontar o `FabricApiUrl` para o endereço certo.*
