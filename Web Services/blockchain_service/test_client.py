import requests
import json
import time

API_URL = "http://localhost:3000"

def run_supply_chain_test():
    print("==================================================================")
    print("  TESTE AVANÇADO: RASTREABILIDADE FÍSICA & SIGILO BILATERAL      ")
    print("  Hyperledger Fabric - Smart Contract 'saip' (Porta 3000)        ")
    print("==================================================================")

    test_batch_id = f"LOTE-MACA-{int(time.time())}"
    print(f"\n[INFO] A utilizar o Lote de Teste: {test_batch_id}")

    # -------------------------------------------------------------------------
    # 1. PRODUTOR JOÃO: Criação do Lote e Venda Inicial ao Distribuidor Silva
    # -------------------------------------------------------------------------
    print("\n--- 1. PRODUTOR JOÃO: Registo da Colheita e Venda ao Distribuidor ---")
    initial_batch_data = {
        "id": test_batch_id,
        "cultureName": "Maçã Gala de Alcobaça",
        "quantityKg": "500.0",
        "harvestDate": "2026-09-16",
        "producerName": "Produtor_Joao",
        "buyerName": "Distribuidor_Silva",
        "plantation_info": {
            "farm": "Quinta dos Pomares",
            "location": "Alcobaça, Portugal",
            "certifications": ["GlobalGAP", "Produção Integrada"],
            "chemical_use": "Mínimo / Sem Resíduos"
        },
        "financial_details": {
            "pricePerKg": "0.80",
            "totalAmount": "400.00",
            "currency": "EUR",
            "paymentTerms": "15 dias"
        }
    }

    r = requests.post(f"{API_URL}/invoke", data={
        "channelid": "mychannel",
        "chaincodeid": "saip",
        "function": "CreateOrder",
        "args": [json.dumps(initial_batch_data), "Produtor_Joao"]
    })
    print(f"Status: {r.status_code}")
    print(f"Resposta: {r.text[:180]}...")
    assert r.status_code == 200 and not r.text.startswith("Error"), "Falha ao criar lote inicial"
    print("-> [OK] Lote e 1ª Venda (0.80 €/kg) registados na Blockchain!")

    # -------------------------------------------------------------------------
    # 2. LOGÍSTICA NORTE: Registo da Etapa de Transporte Físico
    # -------------------------------------------------------------------------
    print("\n--- 2. LOGÍSTICA NORTE: Transporte para o Centro de Distribuição ---")
    transport_details = {
        "vehiclePlate": "AA-11-BB",
        "driver": "Carlos Santos",
        "tempCelsius": "4.2",
        "origin": "Alcobaça",
        "destination": "Armazém Silva, Porto"
    }

    r = requests.post(f"{API_URL}/invoke", data={
        "channelid": "mychannel",
        "chaincodeid": "saip",
        "function": "TransferCustody",
        "args": [test_batch_id, "Logistica_Norte", "IN_TRANSIT", json.dumps(transport_details), "Logistica_Norte"]
    })
    assert r.status_code == 200 and not r.text.startswith("Error"), "Falha ao atualizar custódia"
    print("-> [OK] Evento de Transporte e Temperatura (4.2ºC) adicionado à Cadeia de Custódia!")

    # -------------------------------------------------------------------------
    # 3. DISTRIBUIDOR SILVA: Revenda ao Supermercado Continente (1.50 €/kg)
    # -------------------------------------------------------------------------
    print("\n--- 3. DISTRIBUIDOR SILVA: Revenda Comercial ao Supermercado Continente ---")
    resale_deal = {
        "dealId": f"DEAL-{test_batch_id}-2",
        "sellerId": "Distribuidor_Silva",
        "buyerId": "Supermercado_Continente",
        "financial_details": {
            "pricePerKg": "1.50",
            "totalAmount": "750.00",
            "currency": "EUR",
            "paymentTerms": "30 dias",
            "packaging": "Embalagens Recicláveis 1kg"
        }
    }

    r = requests.post(f"{API_URL}/invoke", data={
        "channelid": "mychannel",
        "chaincodeid": "saip",
        "function": "RecordCommercialDeal",
        "args": [test_batch_id, json.dumps(resale_deal), "Distribuidor_Silva"]
    })
    assert r.status_code == 200 and not r.text.startswith("Error"), "Falha ao registar revenda"
    print("-> [OK] 2ª Venda (1.50 €/kg) registada na Blockchain!")

    # -------------------------------------------------------------------------
    # 4. VALIDAÇÃO DE SIGILO: SUPERMERCADO CONTINENTE
    # -------------------------------------------------------------------------
    print("\n==================================================================")
    print("  4. VALIDAÇÃO DE SEGURANÇA: CONSULTA DO SUPERMERCADO CONTINENTE   ")
    print("==================================================================")
    r = requests.post(f"{API_URL}/query", data={
        "channelid": "mychannel",
        "chaincodeid": "saip",
        "function": "ReadOrder",
        "args": [test_batch_id],
        "callerid": "Supermercado_Continente"
    })
    data = json.loads(r.text.replace("Response: ", ""))
    deals = data.get("commercial_deals", [])

    print(f"Quinta de Origem Visível: {data.get('plantation_info', {}).get('farm')}")
    print(f"Histórico de Custódia Visível: {len(data.get('custody_chain', []))} eventos")
    print(f"Transações Comerciais Acessíveis: {len(deals)}")

    # O Supermercado SÓ pode ver a transação em que é comprador (1.50 €/kg)
    # NÃO pode ver por quanto o Distribuidor comprou ao Produtor (0.80 €/kg)
    prices_seen = [d.get("financial_details", {}).get("pricePerKg") for d in deals]
    print(f"Preços que o Supermercado consegue ver: {prices_seen}")

    assert "1.50" in prices_seen, "Supermercado deveria ver o seu preço de compra de 1.50 €"
    assert "0.80" not in prices_seen, "ALERTA DE SEGURANÇA: Supermercado viu o preço do Produtor!"
    print("-> [SUCESSO DE SIGILO] O Supermercado vê a sua compra (1.50€), mas o preço do Produtor (0.80€) está 100% OCULTO!")

    # -------------------------------------------------------------------------
    # 5. VALIDAÇÃO DE SIGILO: PRODUTOR JOÃO
    # -------------------------------------------------------------------------
    print("\n==================================================================")
    print("  5. VALIDAÇÃO DE SEGURANÇA: CONSULTA DO PRODUTOR JOÃO           ")
    print("==================================================================")
    r = requests.post(f"{API_URL}/query", data={
        "channelid": "mychannel",
        "chaincodeid": "saip",
        "function": "ReadOrder",
        "args": [test_batch_id],
        "callerid": "Produtor_Joao"
    })
    data = json.loads(r.text.replace("Response: ", ""))
    deals = data.get("commercial_deals", [])
    prices_seen = [d.get("financial_details", {}).get("pricePerKg") for d in deals]
    print(f"Preços que o Produtor consegue ver: {prices_seen}")

    assert "0.80" in prices_seen, "Produtor deveria ver o seu preço de venda de 0.80 €"
    assert "1.50" not in prices_seen, "ALERTA DE SEGURANÇA: Produtor viu a margem do Distribuidor!"
    print("-> [SUCESSO DE SIGILO] O Produtor vê a sua venda (0.80€), mas a revenda do Distribuidor (1.50€) está 100% OCULTA!")

    # -------------------------------------------------------------------------
    # 6. VALIDAÇÃO DE SIGILO: CONCORRENTE OU PÚBLICO GERAL (PINGO DOCE / CONSUMIDOR)
    # -------------------------------------------------------------------------
    print("\n==================================================================")
    print("  6. VALIDAÇÃO DE SEGURANÇA: CONSULTA PÚBLICA / CONCORRENTE        ")
    print("==================================================================")
    r = requests.post(f"{API_URL}/query", data={
        "channelid": "mychannel",
        "chaincodeid": "saip",
        "function": "ReadOrder",
        "args": [test_batch_id],
        "callerid": "Supermercado_PingoDoce"
    })
    data = json.loads(r.text.replace("Response: ", ""))
    deals = data.get("commercial_deals", [])

    print(f"Rastreabilidade de Origem Acessível: {data.get('plantation_info', {}).get('farm')} ({data.get('cultureName')})")
    print(f"Certificações de Qualidade Acessíveis: {data.get('plantation_info', {}).get('certifications')}")
    print(f"Transações Comerciais Acessíveis ao Concorrente: {len(deals)}")

    assert len(deals) == 0, "ALERTA DE SEGURANÇA: Terceiro conseguiu ver dados financeiros!"
    print("-> [SUCESSO TOTAL] O concorrente/consumidor tem acesso a 100% da rastreabilidade física, com ZERO segredos comerciais visíveis!")

    print("\n==================================================================")
    print("  🏆 TESTE CONCLUÍDO COM 100% DE SUCESSO EM TODOS OS CRITÉRIOS!   ")
    print("==================================================================")

if __name__ == "__main__":
    run_supply_chain_test()
