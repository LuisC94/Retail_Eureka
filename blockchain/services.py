import hashlib
import json
import datetime
from .models import BlockchainBlock

class BlockchainService:
    """
    Service para Blockchain utilizando Base de Dados PostgreSQL via Django ORM.
    Implementa agregação de lotes e persistência segura.
    """
    
    def generate_dossier_hash(self, data_dict):
        """Cria o Hash SHA-256 do dossier digital (JSON)."""
        dossier_string = json.dumps(data_dict, sort_keys=True, default=str)
        data_hash = hashlib.sha256(dossier_string.encode('utf-8')).hexdigest()
        return data_hash

    def sign_and_submit_block(self, user_role, batch_id, data_hash, event_type, inputs=None):
        """
        Cria, assina e persiste um novo bloco na Base de Dados.
        Suporta Agregação (inputs) para traceabilidade de lotes transformados.
        """
        # 1. Simular Carteiras (Hardcoded para Demo)
        wallets = {
            'Producer': '0xProducerAddressA1B2...',
            'Transporter': '0xTransporterAddressC3D4...',
            'Retailer': '0xRetailerAddressE5F6...',
            'Processor': '0xProcessorAddressG7H8...' # Added Processor Wallet
        }
        signer = wallets.get(user_role, '0xUnknown')
        
        # 2. Obter Hash Anterior (Da BD)
        last_block = BlockchainBlock.objects.order_by('-block_index').first()
        if last_block:
            previous_hash = last_block.block_hash
            new_index = last_block.block_index + 1
        else:
            previous_hash = "00000000000000000000000000000000"
            new_index = 0

        # 3. Preparar Conteúdo para Hash
        # Se houver 'inputs' (agregacao), eles fazem parte da identidade do bloco
        block_content = f"{batch_id}{data_hash}{previous_hash}{signer}{event_type}"
        if inputs:
            # Adiciona os inputs ao string de hash para garantir imutabilidade da genealogia
            inputs_str = json.dumps(inputs, sort_keys=True)
            block_content += inputs_str

        block_hash = hashlib.sha256(block_content.encode()).hexdigest()
        
        # 4. Criar Payload Final (JSON para BD)
        final_data_content = {
            "batch_id": batch_id, # Redundante mas util no JSON
            "inputs": inputs if inputs else [], # Genealogia: Lista de Parents
            "data_hash": data_hash
            # O conteudo original do dossier geralmente estaria aqui ou off-chain.
            # Como a funcao recebe apenas o hash, assumimos que o 'data_hash' é o link.
            # Mas para efeitos de visualizacao, poderiamos passar o 'content' tambem.
        }

        # 5. Persistir na BD
        new_block = BlockchainBlock.objects.create(
            block_index=new_index,
            batch_id=batch_id,
            data_hash=data_hash,
            previous_hash=previous_hash,
            signer=signer,
            role=user_role,
            event_type=event_type,
            block_hash=block_hash,
            data_content=final_data_content
        )
        
        print(f"[Blockchain DB] Bloco #{new_index} minado com sucesso: {block_hash}")
        
        return {
            "status": "Success",
            "tx_hash": block_hash,
            "block_index": new_index
        }

    def get_chain(self):
        """Retorna a cadeia completa (Queryset Values ou List)"""
        return BlockchainBlock.objects.all().values()

# Instância Singleton
blockchain_service = BlockchainService()
