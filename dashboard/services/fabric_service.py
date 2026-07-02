import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Configuração da API Go (Middleware)
import os
FABRIC_API_URL = os.environ.get("FABRIC_API_URL", "http://localhost:3000")

class FabricService:
    """
    Service para comunicar com a API Middleware em Go (Hyperledger Fabric).
    Substitui a simulação local (BlockchainBlock).
    """

    def create_order(self, order_id, producer_id, culture_type, quantity, harvest_date, additional_data=None):
        """
        Cria uma nova 'Order' (Lote) na Blockchain.
        Mapping:
        - orderId -> Harvest ID (ex: "HARVEST-123")
        - orderStatus -> "HARVESTED"
        - producerName -> Producer Username
        - orderProducts -> Lista com detalhes (apenas 1 produto por harvest por agora)
        """
        
        # Endpoint do Middleware (invoke)
        url = f"{FABRIC_API_URL}/invoke"
        
        # Estrutura de Dados conforme esperado pelo Chaincode (CreateOrder)
        # Chaincode: CreateOrder(ctx, orderId, orderStatus, producerName, orderProductsJson)
        
        # 1. Construir o Objeto Order Completo (Dinâmico)
        order_object = {
            "id": str(order_id),
            "orderStatus": "HARVESTED",
            "producerName": str(producer_id),
            "cultureName": culture_type,
            "quantityKg": str(quantity),
            "harvestDate": harvest_date
        }
        
        # 2. Add details from legacy simulation (Solo, Eventos, etc) se existirem
        if additional_data:
            order_object.update(additional_data)
        
        # 3. Preparar Form Data para o Go API (Argumento Único JSON)
        payload = {
            "channelid": "mychannel",
            "chaincodeid": "saip",
            "function": "CreateOrder",
            "args": [json.dumps(order_object)] # Single Argument: JSON String
        }
        
        try:
            # Enviar pedido POST (form-encoded como o Go espera)
            # O Go usa r.ParseForm() e r.Form["args"], que suporta multiplos valores.
            # Aqui enviamos uma lista com 1 string.
            response = requests.post(url, data=payload)
            
            # [CRITICAL UPDATE] O Go API retorna 200 OK mesmo com erro de chaincode.
            # Temos de validar o corpo da resposta.
            if response.status_code == 200 and not response.text.startswith("Error"):
                logger.info(f"[Fabric] CreateOrder Success: {response.text}")
                return {"status": "success", "tx_id": response.text, "payload": payload}
            else:
                logger.error(f"[Fabric] CreateOrder Failed: {response.text}")
                return {"status": "error", "message": response.text}
                
        except Exception as e:
            logger.error(f"[Fabric] Connection Error: {str(e)}")
            return {"status": "error", "message": str(e)}

    
    def update_order(self, order_id, new_status, additional_data=None):
        """
        Atualiza o estado de uma Order existente.
        Permite adicionar campos extras ao JSON (ex: transporte, entrega).
        """
        # 1. Obter o estado atual da Order (READ)
        # Nota: O chaincode UpdateOrder pode exigir o estado completo ou apenas o delta dependendo da implementação. 
        # Assumindo que o chaincode faz merge ou substitui.
        # Se for substituição total, precisamos ler antes.
        try:
            current_state = self.get_order(order_id)
            if not current_state:
                return {"status": "error", "message": f"Order {order_id} not found on chain."}

            # 2. Atualizar campos
            current_state['orderStatus'] = new_status
            
            # 3. Merge de dados adicionais (ex: transporter info)
            if additional_data:
                current_state.update(additional_data)

            # 4. Enviar atualização (Invoke UpdateOrder)
            # Chaincode: UpdateOrder(ctx, orderId, orderJson)
            url = f"{FABRIC_API_URL}/invoke"
            
            payload = {
                "channelid": "mychannel",
                "chaincodeid": "saip",
                "function": "UpdateOrder",
                "args": [
                    order_id, 
                    json.dumps(current_state) 
                ]
            }
            
            response = requests.post(url, data=payload)
            
            if response.status_code == 200 and not response.text.startswith("Error"):
                logger.info(f"[Fabric] UpdateOrder Success: {response.text}")
                return {"status": "success", "tx_id": response.text}
            else:
                logger.error(f"[Fabric] UpdateOrder Failed: {response.text}")
                return {"status": "error", "message": response.text}

        except Exception as e:
            logger.error(f"[Fabric] Update Error: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_order(self, order_id):
        """
        Lê o estado atual de uma Order (ReadOrder).
        """
        url = f"{FABRIC_API_URL}/query"
        params = {
            "channelid": "mychannel",
            "chaincodeid": "saip",
            "function": "ReadOrder",
            "args": order_id
        }
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                 # Remove prefixo "Response: " se existir
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

    def get_asset_history(self, order_id):
        """
        [NEW] Obtém o histórico completo de alterações (GetHistoryForAsset).
        """
        url = f"{FABRIC_API_URL}/query"
        params = {
            "channelid": "mychannel",
            "chaincodeid": "saip",
            "function": "GetHistoryForAsset",
            "args": order_id
        }
        
        try:
            response = requests.get(url, params=params)
            
            # The Go API returns "Response: [...]" or "Error: ..."
            # We need to clean this up.
            if response.status_code == 200:
                resp_text = response.text
                
                # Check for "Error: " prefix
                if resp_text.startswith("Error:"):
                    logger.error(f"[Fabric] History Error from API: {resp_text}")
                    return []
                
                # Strip "Response: " prefix if present
                if resp_text.startswith("Response:"):
                    json_str = resp_text.replace("Response:", "", 1).strip()
                else:
                    json_str = resp_text
                    
                # Parse JSON
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    # Tentar limpar caracteres estranhos (o Go as vezes retorna bytes stringified)
                    logger.error(f"[Fabric] JSON Decode Error: {e} | Content: {json_str[:100]}...")
                    return []
                    
            return []
        except Exception as e:
            logger.error(f"[Fabric] Connection Error: {str(e)}")
            return []

fabric_service = FabricService()
