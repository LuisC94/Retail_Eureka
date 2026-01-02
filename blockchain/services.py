import hashlib
import json
import datetime

class BlockchainService:
    """
    MOCK Service para simular Blockchain sem dependências complexas.
    Funciona como uma 'Ledger' imutável em memória ou ficheiro local.
    """
    
    def __init__(self):
        # Em memória para demonstração. Num cenário real, ligaria ao Besu/Ganache.
        self.chain = []
        # Armazena os dados "Off-Chain" para visualização. 
        # Na realidade estariam numa BD, mas aqui guardamos associados ao hash.
        self.off_chain_storage = {} 
        
    def generate_dossier_hash(self, data_dict):
        """Cria o Hash SHA-256 do dossier digital (JSON)."""
        dossier_string = json.dumps(data_dict, sort_keys=True)
        data_hash = hashlib.sha256(dossier_string.encode('utf-8')).hexdigest()
        
        # Guardar para visualização futura (Simulando a BD)
        self.off_chain_storage[data_hash] = data_dict
        
        return data_hash

    def sign_and_submit_block(self, user_role, batch_id, data_hash, event_type):
        """
        Simula a assinatura e submissão de um bloco.
        """
        # Simular carteiras
        wallets = {
            'Producer': '0xProducerAddressA1B2...',
            'Transporter': '0xTransporterAddressC3D4...',
            'Retailer': '0xRetailerAddressE5F6...'
        }
        
        signer = wallets.get(user_role, '0xUnknown')
        
        # Simular o "Bloco Anterior" (Previous Hash)
        previous_hash = "00000000000000000000000000000000"
        if self.chain:
            previous_hash = self.chain[-1]['block_hash']

        # Criar o Bloco
        block_content = f"{batch_id}{data_hash}{previous_hash}{signer}{event_type}"
        block_hash = hashlib.sha256(block_content.encode()).hexdigest()
        
        # Recuperar os dados originais se existirem
        original_data = self.off_chain_storage.get(data_hash, {})

        new_block = {
            "block_index": len(self.chain) + 1,
            "batch_id": batch_id,
            "data_hash": data_hash,
            "previous_hash": previous_hash,
            "signer": signer,
            "role": user_role,
            "event_type": event_type,
            "timestamp": datetime.datetime.now().isoformat(),
            "block_hash": block_hash,  # O "Selo" final do bloco
            "content": original_data # Apenas para visualização no Explorer
        }
        
        self.chain.append(new_block)
        
        print(f"[Blockchain Mock] Bloco minado com sucesso: {block_hash}")
        
        return {
            "status": "Success",
            "tx_hash": block_hash,
            "signer": signer,
            "block_data": new_block
        }

    def get_chain(self):
        return self.chain
