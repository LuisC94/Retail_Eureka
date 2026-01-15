
import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from blockchain.services import blockchain_service
from dashboard.models import MarketplaceOrder

def debug_chain(start_batch_id):
    print(f"--- Debugging Chain for: {start_batch_id} ---")
    full_chain = blockchain_service.get_chain()
    print(f"Total Block in Chain: {len(full_chain)}")

    visited = set()
    
    def fetch_genealogy(current_batch_id, depth=0):
        indent = "  " * depth
        print(f"{indent}> Visiting: {current_batch_id}")
        
        if current_batch_id in visited:
            print(f"{indent}  (Already visited)")
            return []
        visited.add(current_batch_id)
        
        my_blocks = [b for b in full_chain if b['batch_id'] == current_batch_id]
        print(f"{indent}  Found {len(my_blocks)} blocks for this ID.")
        
        parents_found = False
        
        # B. Explore Inputs
        for block in my_blocks:
            content = block.get('data_content', {}) or {}
            inputs = content.get('inputs', [])
            
            # Print keys to see what's inside
            print(f"{indent}  Block {block['block_hash'][:8]} keys: {list(content.keys())}")
            
            if inputs:
                print(f"{indent}  Has Inputs: {inputs}")
                for inp in inputs:
                    pid = inp.get('batch_id')
                    if pid:
                        parents_found = True
                        fetch_genealogy(pid, depth + 1)

            harvest_origin = content.get('harvest_origin')
            if not harvest_origin and 'order' in content:
                 harvest_origin = content['order'].get('harvest_origin')
            
            if harvest_origin and str(harvest_origin) != "N/A":
                print(f"{indent}  Has Harvest Origin: {harvest_origin}")
                parents_found = True
                pid = f"LOTE-{harvest_origin}" if not str(harvest_origin).startswith('LOTE-') else harvest_origin
                fetch_genealogy(pid, depth + 1)
        
        # C. Fallback Check
        print(f"{indent}  Fallback Check: startswith('ORDER-')={current_batch_id.startswith('ORDER-')}, Any Previous Hash!=0? {any(str(b.get('previous_hash')) != '0' for b in my_blocks)}")
        
        if current_batch_id.startswith('ORDER-') and not any(str(b.get('previous_hash')) != '0' for b in my_blocks):
             print(f"{indent}  TRIGGERING DB FALLBACK...")
             try:
                order_pk = current_batch_id.replace('ORDER-', '')
                order_obj = MarketplaceOrder.objects.filter(pk=order_pk).first()
                if order_obj:
                    print(f"{indent}    Order Found in DB. Origin: {order_obj.harvest_origin}")
                    if order_obj.harvest_origin:
                        parents_found = True
                        pid = f"LOTE-{order_obj.harvest_origin.pk}"
                        fetch_genealogy(pid, depth + 1)
                else:
                    print(f"{indent}    Order NOT found in DB.")
             except Exception as e:
                 print(f"{indent}    Error in fallback: {e}")
        else:
             print(f"{indent}  Fallback skipped (Condition not met)")

    fetch_genealogy(start_batch_id)

if __name__ == "__main__":
    full_chain = blockchain_service.get_chain()
    print(f"Total blocks in DB: {len(full_chain)}")
    
    target_id = "ORDER-50"
    print(f"Scanning for blocks with batch_id='{target_id}'...")
    
    found_blocks = [b for b in full_chain if b['batch_id'] == target_id]
    print(f"Found {len(found_blocks)} blocks for {target_id}")
    
    for b in found_blocks:
        print(f" - {b['event_type']} | Hash: {b['block_hash'][:8]}")
        print(f"   Content: {b.get('data_content', 'MISSING')}")

    # Also check LOTE-PROC-50 definition
    proc_block = next((b for b in full_chain if b['batch_id'] == 'LOTE-PROC-50'), None)
    if proc_block:
        print(f"\nScanning LOTE-PROC-50:")
        print(f" - Inputs: {proc_block['data_content'].get('inputs')}")
        debug_chain('LOTE-PROC-50')
    else:
        print("\nLOTE-PROC-50 not found.")
