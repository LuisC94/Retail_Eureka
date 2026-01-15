from django.db import models

class BlockchainBlock(models.Model):
    block_index = models.IntegerField(verbose_name="Block Height")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Identificadores de Negócio
    batch_id = models.CharField(max_length=100, verbose_name="Batch ID")
    
    # Criptografia
    data_hash = models.CharField(max_length=64, verbose_name="Data Hash (SHA256)")
    previous_hash = models.CharField(max_length=64, verbose_name="Previous Hash")
    block_hash = models.CharField(max_length=64, unique=True, verbose_name="Block Hash")
    
    # Metadados de Autoria
    signer = models.CharField(max_length=100, verbose_name="Signer Wallet/ID")
    role = models.CharField(max_length=50, verbose_name="User Role")
    event_type = models.CharField(max_length=50, verbose_name="Event Type")
    
    # Dados (Payload) - Armazena o Dossier completo e Inputs para agregação
    data_content = models.JSONField(verbose_name="Block Data (JSON)")

    class Meta:
        db_table = 'blockchain_blocks'
        ordering = ['block_index']
        verbose_name = 'Blockchain Block'
        verbose_name_plural = 'Blockchain Blocks'

    def __str__(self):
        return f"Block #{self.block_index} [{self.block_hash[:8]}] - {self.event_type}"
