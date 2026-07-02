# Análise de Integração Blockchain <-> Plataforma SAIP

Este documento explica tecnicamente como a tua plataforma (.NET) fala com a Blockchain e o que é necessário para tudo funcionar em conjunto.

## 1. O Fluxo de Dados (The Bridge)

A tua arquitetura usa um modelo de **3 Camadas**:

`Frontend (Angular)` -> `Backend (.NET)` -> `Middleware (Go API)` -> `Blockchain (Fabric)`

### Passo A: O Backend Envia o Pedido (`FabricService.cs`)
No ficheiro `OrderManagement/Services/FabricService.cs`, o teu backend atua como um cliente HTTP. Ele não fala diretamente com a Blockchain (o que é bom, pois simplifica o .NET).

*   **O que ele faz:** Cria um JSON com os dados da encomenda e envia para uma URL.
*   **Código Chave:**
    ```csharp
    // FabricService.cs
    HttpResponseMessage response = await client.PostAsync(_configuration["AppSettings:FabricApiUrl"] + "/invoke", content);
    ```
*   **Configuração:** O IP de destino está em `appsettings.json`:
    ```json
    "FabricApiUrl": "http://192.168.126.14:3000" // ATENÇÃO: Isto terá de ser mudado para localhost ou IP do WSL
    ```

### Passo B: O Middleware Recebe e Traduz (`app.go` + `invoke.go`)
A API em Go (que corre no porto 3000) serve de tradutor. Ela tem as bibliotecas oficiais do Hyperledger Fabric (SDK).

*   **O que ele faz:**
    1.  Recebe o pedido HTTP do .NET.
    2.  Usa a "Chave Mestra" (User1) para se autenticar na rede.
    3.  Envia a transação para o `peer0.org1` via gRPC.
*   **Código Chave:**
    ```go
    // invoke.go
    contract := network.GetContract(chainCodeName)
    txn_proposal, err := contract.NewProposal(function, client.WithArguments(args...))
    ```

### Passo C: O Smart Contract Executa (`chaincode.js`)
Finalmente, o código que está *dentro* da rede Blockchain executa a lógica de negócio.

*   **O que ele faz:** Verifica se a encomenda já existe e grava no "Livro de Registos" imutável.
*   **Código Chave:**
    ```javascript
    // chaincode.js
    async CreateOrder(ctx, orderJSON) {
        ...
        await ctx.stub.putState(order.id, ...); // Grava no Ledger
    }
    ```

---

## 2. O que é preciso para criar o Blockchain?

Para que este ecossistema funcione, "criar o blockchain" significa levantar a infraestrutura onde o **Passo C** vive.

### Os Ingredientes (Docker Containers)
Tu não crias o blockchain "do zero" em código C# ou Go. Tu **configuras** uma rede de servidores. Os scripts que corremos (`network.sh up ...`) levantam estes 3 pilares:

1.  **Peer (O Guarda-Livros):** O servidor que guarda a cópia da blockchain. É aqui que o `chaincode.js` é instalado.
2.  **Orderer (O Notário):** O servidor que recebe as transações de toda a gente, ordena-as por cronologia e cria os blocos.
3.  **CA (O Cartório):** O servidor que emite os certificados digitais para que o **Passo B** (Go API) consiga provar que tem permissão para falar com o Peer.

## 3. Como integrar com a tua plataforma?

Para a tua plataforma "falar" com o Blockchain, tens de garantir 3 coisas:

1.  **Conectividade de Rede:**
    *   O Backend .NET tem de conseguir chegar ao IP do Middleware Go (Porta 3000).
    *   O Middleware Go tem de conseguir chegar aos Containers Docker (Portas 7051 e 9051). *Isto já está configurado no `main.go`*.

2.  **Alinhamento de Dados:**
    *   O JSON que o .NET envia (`Order` object) tem de ter **exatamente** os campos que o `chaincode.js` espera ler. Se o .NET enviar `ProductId` e o Chaincode esperar `product_id`, vai dar erro.

3.  **Configuração de IPs:**
    *   No teu `appsettings.json`, o `FabricApiUrl` está com um IP fixo (`192.168...`).
    *   Como estás a rodar tudo localmente (WSL), deves mudar para `http://localhost:3000`.

### Resumo para o teu Trabalho
*   **Ficheiros a Manter:** Não precisas de mudar o código do Chaincode nem do Go (já estão feitos para funcionar um com o outro).
*   **Ficheiros a Ajustar:** Apenas o `appsettings.json` do .NET para apontar para o sítio certo.
*   **Onde está a "Magia":** Está no `FabricService.cs`. É ele o único ponto de contacto entre o teu mundo clássico (.NET) e o mundo Blockchain.
