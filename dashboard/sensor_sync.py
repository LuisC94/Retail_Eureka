import threading
import time
import requests
import json
import csv
import os
from django.conf import settings

def start_sensor_sync_thread():
    def sync_loop():
        # Aguarda 5 segundos para que o processo principal inicialize completamente
        time.sleep(5)
        url = "https://docs.google.com/spreadsheets/d/13qQPIxbvm0aIjWB57CqSMSBQa7tx_DfYI4rColx41hI/export?format=csv"
        cache_path = os.path.join(settings.BASE_DIR, 'dashboard', 'sensor_cache.json')
        
        while True:
            try:
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    response.encoding = 'utf-8'
                    lines = response.text.splitlines()
                    reader = csv.reader(lines)
                    rows = list(reader)
                    if len(rows) > 1:
                        headers = rows[0]
                        data_rows = rows[1:]
                        # Reverter para obter os mais recentes primeiro
                        data_rows.reverse()
                        
                        # Mapear cabeçalhos para valores e limitar a 100 leituras
                        formatted_data = []
                        for r in data_rows[:100]:
                            if len(r) == len(headers):
                                formatted_data.append(dict(zip(headers, r)))
                        
                        # Gravação segura do JSON
                        payload = {
                            'status': 'success',
                            'headers': headers,
                            'data': formatted_data,
                            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                        with open(cache_path, 'w', encoding='utf-8') as f:
                            json.dump(payload, f, indent=4)
                        
                        print("[Sensor Sync] Cache de sensores atualizado com sucesso do Google Sheets.")
                    else:
                        print("[Sensor Sync] Google Sheet vazio ou sem dados.")
                else:
                    print(f"[Sensor Sync] Erro: Google Sheet retornou status {response.status_code}")
            except Exception as e:
                print(f"[Sensor Sync] Exceção durante a sincronização: {str(e)}")
            
            # Sincroniza a cada 10 minutos (600 segundos)
            time.sleep(600)

    # Inicia como daemon para terminar quando o processo principal do Django terminar
    t = threading.Thread(target=sync_loop, daemon=True)
    t.start()
