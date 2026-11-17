import requests
import json
import logging
from django.conf import settings
import os

logger = logging.getLogger(__name__)

# Configuração da API Go (Middleware)
FABRIC_API_URL = getattr(settings, 'FABRIC_API_URL', os.environ.get("FABRIC_API_URL", "http://localhost:3000"))

class FabricService:
    """
    Service para comunicar com a API Middleware em Go (Hyperledger Fabric).
    Suporta Rastreabilidade Física Pública e Sigilo Comercial Bilateral por Interveniente.
    """
    backend = "fabric"
    label = "Blockchain (Hyperledger Fabric)"

    def create_order(self, order_id, producer_id, culture_type, quantity, harvest_date, additional_data=None, financial_data=None, buyer_id=None):
        """
        Cria uma nova 'Order' (Lote) na Blockchain.
        Suporta envelope público (rastreabilidade) e envelope privado (comercial).
        """
        url = f"{FABRIC_API_URL}/invoke"
        
        # 1. Construir o Objeto Order Completo (Dinâmico)
        order_object = {
            "id": str(order_id),
            "orderStatus": "HARVESTED",
            "producerName": str(producer_id),
            "buyerName": str(buyer_id) if buyer_id else "DISTRIBUTOR",
            "cultureName": culture_type,
            "quantityKg": str(quantity),
            "harvestDate": harvest_date
        }
        
        # 2. Adicionar envelope público adicional se existir (Solo, Eventos, Certificações)
        if additional_data:
            order_object["plantation_info"] = additional_data
        
        # 3. Adicionar envelope financeiro confidencial se existir
        if financial_data:
            order_object["financial_details"] = financial_data
        
        # 4. Preparar Form Data para o Go API
        payload = {
            "channelid": "mychannel",
            "chaincodeid": "saip",
            "function": "CreateOrder",
            "args": [json.dumps(order_object), str(producer_id)]
        }
        
        try:
            response = requests.post(url, data=payload, timeout=15)
            if response.status_code == 200 and not response.text.startswith("Error"):
                logger.info(f"[Fabric] CreateOrder Success: {response.text}")
                return {"status": "success", "tx_id": response.text, "payload": payload}
            else:
                logger.error(f"[Fabric] CreateOrder Failed: {response.text}")
                return {"status": "error", "message": response.text}
                
        except Exception as e:
            logger.error(f"[Fabric] Connection Error: {str(e)}")
            return {"status": "error", "message": str(e)}

    def transfer_custody(self, order_id, actor_id, action, details=None):
        """
        Regista uma nova movimentação física na Cadeia de Custódia (Pública).
        Ex: action = 'IN_TRANSIT', 'WAREHOUSE_IN', 'DELIVERED'.
        """
        url = f"{FABRIC_API_URL}/invoke"
        payload = {
            "channelid": "mychannel",
            "chaincodeid": "saip",
            "function": "TransferCustody",
            "args": [str(order_id), str(actor_id), str(action), json.dumps(details or {}), str(actor_id)]
        }
        try:
            response = requests.post(url, data=payload, timeout=15)
            if response.status_code == 200 and not response.text.startswith("Error"):
                return {"status": "success", "tx_id": response.text}
            return {"status": "error", "message": response.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def record_commercial_deal(self, order_id, seller_id, buyer_id, financial_details):
        """
        Regista uma nova venda/revenda comercial privada para o lote.
        Valores financeiros são estritamente sigilosos entre seller_id e buyer_id.
        """
        url = f"{FABRIC_API_URL}/invoke"
        deal_object = {
            "dealId": f"DEAL-{order_id}-{seller_id}-{buyer_id}",
            "sellerId": str(seller_id),
            "buyerId": str(buyer_id),
            "financial_details": financial_details
        }
        payload = {
            "channelid": "mychannel",
            "chaincodeid": "saip",
            "function": "RecordCommercialDeal",
            "args": [str(order_id), json.dumps(deal_object), str(seller_id)]
        }
        try:
            response = requests.post(url, data=payload, timeout=15)
            if response.status_code == 200 and not response.text.startswith("Error"):
                return {"status": "success", "tx_id": response.text}
            return {"status": "error", "message": response.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def update_order(self, order_id, new_status, additional_data=None, caller_id=None):
        """
        Atualiza o estado de uma Order existente.

        Usa UpdateOrderStatus: o chaincode parte do estado COMPLETO gravado no ledger e só altera
        o estado e os campos adicionais. Antes, o estado era lido aqui já filtrado pelo sigilo do
        caller_id e gravado de volta, o que apagava os negócios de terceiros do lote.
        """
        try:
            url = f"{FABRIC_API_URL}/invoke"
            payload = {
                "channelid": "mychannel",
                "chaincodeid": "saip",
                "function": "UpdateOrderStatus",
                "args": [
                    str(order_id),
                    str(new_status),
                    json.dumps(additional_data or {}, default=str),
                    str(caller_id or "")
                ]
            }

            response = requests.post(url, data=payload, timeout=15)
            if response.status_code == 200 and not response.text.startswith("Error"):
                logger.info(f"[Fabric] UpdateOrderStatus Success: {response.text}")
                return {"status": "success", "tx_id": response.text}
            else:
                logger.error(f"[Fabric] UpdateOrderStatus Failed: {response.text}")
                if "does not exist" in response.text:
                    return {"status": "error", "message": f"Order {order_id} not found on chain."}
                return {"status": "error", "message": response.text}

        except Exception as e:
            logger.error(f"[Fabric] Update Error: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_order(self, order_id, caller_id=None):
        """
        Lê o estado de um Lote aplicando o filtro de sigilo conforme o caller_id.
        """
        url = f"{FABRIC_API_URL}/query"
        payload = {
            "channelid": "mychannel",
            "chaincodeid": "saip",
            "function": "ReadOrder",
            "args": [str(order_id)],
            "callerid": str(caller_id or "")
        }
        
        try:
            response = requests.post(url, data=payload, timeout=15)
            if response.status_code == 200:
                clean_text = response.text
                if clean_text.startswith("Response:"):
                    clean_text = clean_text.replace("Response:", "", 1).strip()
                
                try:
                    return json.loads(clean_text)
                except json.JSONDecodeError:
                    logger.error(f"[Fabric] JSON Decode Error: {response.text}")
                    return None
            return None
        except Exception:
            return None

    def get_all_orders(self, caller_id=None):
        """
        Retorna todos os lotes aplicando filtragem de sigilo comercial para o caller_id.
        """
        url = f"{FABRIC_API_URL}/query"
        payload = {
            "channelid": "mychannel",
            "chaincodeid": "saip",
            "function": "GetAllOrders",
            "callerid": str(caller_id or "")
        }
        try:
            response = requests.post(url, data=payload, timeout=15)
            if response.status_code == 200:
                clean_text = response.text.replace("Response:", "", 1).strip()
                return json.loads(clean_text)
            return []
        except Exception:
            return []

    def get_asset_history(self, order_id, caller_id=None):
        """
        Obtém o histórico imutável completo de alterações na Blockchain (GetOrderHistory).
        Cada versão vem filtrada pelo sigilo comercial conforme o caller_id
        (sem caller_id = consulta pública, sem dados comerciais).
        """
        url = f"{FABRIC_API_URL}/query"
        payload = {
            "channelid": "mychannel",
            "chaincodeid": "saip",
            "function": "GetOrderHistory",
            "args": [str(order_id)],
            "callerid": str(caller_id or "")
        }
        
        try:
            response = requests.post(url, data=payload, timeout=15)
            if response.status_code == 200:
                resp_text = response.text
                if resp_text.startswith("Error:"):
                    logger.error(f"[Fabric] History Error from API: {resp_text}")
                    return []
                
                json_str = resp_text.replace("Response:", "", 1).strip() if resp_text.startswith("Response:") else resp_text
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"[Fabric] JSON Decode Error: {e} | Content: {json_str[:100]}...")
                    return []
            return []
        except Exception as e:
            logger.error(f"[Fabric] Connection Error: {str(e)}")
            return []

def build_ledger_service():
    """
    Escolhe o motor do ledger conforme settings.LEDGER_BACKEND ("fabric" ou "local").
    O resto da plataforma usa sempre `fabric_service` e não precisa de saber qual está ativo.
    """
    backend = str(getattr(settings, 'LEDGER_BACKEND', 'fabric')).strip().lower()
    if backend == 'local':
        from dashboard.services.local_ledger_service import LocalLedgerService
        logger.info("[Ledger] Motor ativo: LOCAL (tabela LedgerEntry)")
        return LocalLedgerService()
    if backend != 'fabric':
        logger.warning(f"[Ledger] LEDGER_BACKEND desconhecido '{backend}', a usar 'fabric'.")
    return FabricService()


fabric_service = build_ledger_service()
