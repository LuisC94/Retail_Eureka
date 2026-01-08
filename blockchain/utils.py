from dashboard.models import Warehouse, PlantationEvent

def create_genesis_dossier(harvest):
    """
    Gera o dossier digital (Genesis) para uma colheita.
    Reutilizável para chamadas manuais ou automáticas.
    """
    plantation = harvest.plantation
    
    # A. Informação da Plantação (Origem)
    plantation_info = {
        "name": plantation.plantation_name if plantation else "N/A",
        "location": plantation.location if plantation else "Unknown",
        "area_m2": float(plantation.area) if plantation else 0,
        "production_type": plantation.get_production_type_display() if plantation else "N/A",
        "chemical_use": plantation.get_chemical_use_display() if plantation else "N/A",
        "soil_type": plantation.get_soil_type_display() if plantation else "Unknown",
        "water_regime": plantation.get_water_regime_display() if plantation else "Unknown"
    }

    # B. Informação do Armazém (Onde está guardado atualmente)
    # Tenta encontrar uma Warehouse do produtor
    warehouse = Warehouse.objects.filter(owner=harvest.producer).first()
    warehouse_info = {
        "id": warehouse.warehouse_id if warehouse else "N/A",
        "location": warehouse.location if warehouse else "Unknown",
        "type": warehouse.get_control_type_display() if warehouse else "N/A",
        "has_sensors": "Yes" if warehouse and warehouse.sensors.exists() else "No"
    }

    # C. Histórico de Eventos (Rastreabilidade Completa e Detalhada)
    events = PlantationEvent.objects.filter(plantation=plantation)
    event_history = []
    
    for event in events:
        event_entry = {
            "date": event.event_date.strftime('%Y-%m-%d'),
            "type": event.get_event_type_display(),
            "notes": event.notes
        }

        # Extração de Detalhes Técnicos baseada no tipo
        if event.fertilizer_synth:
            f = event.fertilizer_synth
            event_entry["tech_details"] = {
                "product": f.commercial_product,
                "npk": f.form_npk,
                "dose": f"{f.total_dose_kg_ha_year} kg/ha/year"
            }
        elif event.fertilizer_org:
            f = event.fertilizer_org
            event_entry["tech_details"] = {
                "type": f.organic_fertilizer_type,
                "origin": f.origin,
                "dose": f"{f.dose_tha_year} t/ha/year"
            }
        elif event.soil_corrective:
            s = event.soil_corrective
            event_entry["tech_details"] = {
                "product": s.commercial_product,
                "type": s.corrective_type,
                "dose": f"{s.dose_kg_ha_year} kg/ha/year"
            }
        elif event.pest_control:
            p = event.pest_control
            event_entry["tech_details"] = {
                "product": p.commercial_product,
                "active_substance": p.active_substance,
                "target": p.pest_type,
                "dose": p.dose_per_application
            }
        # Adicionar mais condições se necessário

        event_history.append(event_entry)
        
    # D. Dossier Final Consolidado
    dossier = {
        "batch_id": f"LOTE-{harvest.harvest_id}",
        "producer_id": harvest.producer.username,
        "creation_date": harvest.harvest_date.strftime('%Y-%m-%d'),
        
        "harvest": {
            "product": harvest.subfamily.name if harvest.subfamily else "N/A",
            "quantity_kg": float(harvest.harvest_quantity_kg),
            "quality_score": harvest.avg_quality_score,
            "origin_plantation": plantation.plantation_name if plantation else "N/A",
            "caliber_mm": float(harvest.caliber) if harvest.caliber else "N/A",
            "soluble_solids_brix": float(harvest.soluble_solids) if harvest.soluble_solids else "N/A"
        },
        
        "plantation": plantation_info,
        "storage": warehouse_info,
        "events_log": event_history
    }
    
    return dossier
