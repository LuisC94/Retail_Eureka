"""
Ledger local: alternativa ao Hyperledger Fabric, ativada com LEDGER_BACKEND="local".

Expõe a mesma interface e o mesmo formato de resposta que o FabricService, e replica
a lógica do chaincode 'saip' (Web Services/blockchain_service/chaincode/chaincode.js),
incluindo o filtro de sigilo comercial. As transações ficam na tabela LedgerEntry,
encadeadas por hash SHA-256 (ver o comando `python manage.py verify_ledger`).
"""
import copy
import hashlib
import json
import logging
import uuid
from datetime import timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

GENESIS_PREV_HASH = "0" * 64
MAX_APPEND_RETRIES = 5


def _canonical(data):
    """JSON determinístico (chaves ordenadas), equivalente ao stringify(sortKeysRecursive())."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalize(data):
    """Garante que o estado é JSON puro (datas, Decimals, etc. passam a string)."""
    return json.loads(json.dumps(data, default=str))


def _iso(dt):
    return dt.astimezone(dt_timezone.utc).isoformat()


def compute_entry_hash(block_number, prev_hash, tx_id, asset_id, function, actor, timestamp, state):
    payload = _canonical({
        "block_number": block_number,
        "prev_hash": prev_hash,
        "tx_id": tx_id,
        "asset_id": asset_id,
        "function": function,
        "actor": actor,
        "timestamp": _iso(timestamp),
        "state": state,
    })
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def filter_order_privacy(order, caller_id):
    """Cópia fiel do filterOrderPrivacy do chaincode."""
    if not order:
        return order
    filtered = copy.deepcopy(order)
    caller = str(caller_id or "").strip()

    if isinstance(filtered.get("commercial_deals"), list):
        if caller in ("Admin", "Auditor"):
            pass
        elif caller:
            filtered["commercial_deals"] = [
                d for d in filtered["commercial_deals"]
                if d and (d.get("sellerId") == caller or d.get("buyerId") == caller)
            ]
        else:
            filtered["commercial_deals"] = []

    filtered.pop("financial_details", None)

    if filtered.get("private_data"):
        authorized = bool(caller) and (
            caller in ("Admin", "Auditor")
            or caller == filtered.get("producerName")
            or caller == filtered.get("buyerName")
            or caller in (filtered.get("authorized_parties") or [])
        )
        if not authorized:
            filtered["private_data"] = {}

    return filtered


class LocalLedgerService:
    backend = "local"
    label = "Registo de Rastreabilidade (Ledger Local)"

    # ------------------------------------------------------------------
    # Infraestrutura do ledger
    # ------------------------------------------------------------------

    def _latest_state(self, asset_id):
        from dashboard.models import LedgerEntry
        entry = LedgerEntry.objects.filter(asset_id=asset_id).order_by("-block_number").first()
        return copy.deepcopy(entry.state) if entry else None

    def _append(self, asset_id, function, actor, state):
        """
        Acrescenta uma entrada ao fim da cadeia. Se duas escritas concorrentes tentarem
        usar o mesmo bloco pai, as constraints unique fazem uma delas falhar e voltar a tentar.
        """
        from dashboard.models import LedgerEntry

        state = _normalize(state)
        for _ in range(MAX_APPEND_RETRIES):
            last = LedgerEntry.objects.order_by("-block_number").first()
            block_number = (last.block_number + 1) if last else 0
            prev_hash = last.hash if last else GENESIS_PREV_HASH
            tx_id = uuid.uuid4().hex
            ts = timezone.now()
            entry_hash = compute_entry_hash(block_number, prev_hash, tx_id, asset_id, function, actor, ts, state)
            try:
                with transaction.atomic():
                    return LedgerEntry.objects.create(
                        block_number=block_number, tx_id=tx_id, asset_id=asset_id,
                        function=function, actor=actor, timestamp=ts, state=state,
                        prev_hash=prev_hash, hash=entry_hash,
                    )
            except IntegrityError:
                logger.info("[LocalLedger] Conflito de concorrência no bloco %s, a repetir.", block_number)
        raise RuntimeError("Não foi possível acrescentar a entrada ao ledger local (concorrência).")

    def _success(self, entry, payload=None):
        result = {"status": "success", "tx_id": entry.tx_id}
        if payload is not None:
            result["payload"] = payload
        return result

    # ------------------------------------------------------------------
    # Interface igual à do FabricService
    # ------------------------------------------------------------------

    def create_order(self, order_id, producer_id, culture_type, quantity, harvest_date,
                     additional_data=None, financial_data=None, buyer_id=None):
        order = {
            "id": str(order_id),
            "orderStatus": "HARVESTED",
            "producerName": str(producer_id),
            "buyerName": str(buyer_id) if buyer_id else "DISTRIBUTOR",
            "cultureName": culture_type,
            "quantityKg": str(quantity),
            "harvestDate": harvest_date,
        }
        if additional_data:
            order["plantation_info"] = additional_data
        if financial_data:
            order["financial_details"] = financial_data

        try:
            if self._latest_state(order["id"]) is not None:
                return {"status": "error", "message": f"The order {order['id']} already exists"}

            timestamp = order.get("harvestDate") or _iso(timezone.now())
            order["custody_chain"] = [{
                "timestamp": timestamp,
                "actorId": order["producerName"],
                "action": "HARVEST",
                "details": order.get("plantation_info") or {"description": "Colheita Inicial do Lote"},
            }]
            order["commercial_deals"] = []
            if order.get("financial_details"):
                order["commercial_deals"].append({
                    "dealId": f"DEAL-{order['id']}-1",
                    "sellerId": order["producerName"],
                    "buyerId": order["buyerName"],
                    "financial_details": order["financial_details"],
                    "timestamp": timestamp,
                })
            order.pop("financial_details", None)

            entry = self._append(order["id"], "CreateOrder", str(producer_id), order)
            logger.info("[LocalLedger] CreateOrder %s -> %s", order["id"], entry.tx_id)
            return self._success(entry, payload={"function": "CreateOrder", "order": order})
        except Exception as e:
            logger.error("[LocalLedger] CreateOrder Failed: %s", e)
            return {"status": "error", "message": str(e)}

    def transfer_custody(self, order_id, actor_id, action, details=None):
        try:
            order = self._latest_state(str(order_id))
            if order is None:
                return {"status": "error", "message": f"Order {order_id} does not exist"}
            order.setdefault("custody_chain", []).append({
                "timestamp": _iso(timezone.now()),
                "actorId": str(actor_id or "UNKNOWN_ACTOR"),
                "action": action,
                "details": details or {},
            })
            order["orderStatus"] = action
            order["currentStatus"] = action
            entry = self._append(str(order_id), "TransferCustody", str(actor_id), order)
            return self._success(entry)
        except Exception as e:
            logger.error("[LocalLedger] TransferCustody Failed: %s", e)
            return {"status": "error", "message": str(e)}

    def record_commercial_deal(self, order_id, seller_id, buyer_id, financial_details):
        try:
            order = self._latest_state(str(order_id))
            if order is None:
                return {"status": "error", "message": f"Order {order_id} does not exist"}
            deals = order.setdefault("commercial_deals", [])
            deals.append({
                "dealId": f"DEAL-{order_id}-{seller_id}-{buyer_id}",
                "sellerId": str(seller_id),
                "buyerId": str(buyer_id),
                "financial_details": financial_details,
                "timestamp": _iso(timezone.now()),
            })
            entry = self._append(str(order_id), "RecordCommercialDeal", str(seller_id), order)
            return self._success(entry)
        except Exception as e:
            logger.error("[LocalLedger] RecordCommercialDeal Failed: %s", e)
            return {"status": "error", "message": str(e)}

    def update_order(self, order_id, new_status, additional_data=None, caller_id=None):
        try:
            # Parte do estado completo (não filtrado), para não perder negócios de terceiros.
            order = self._latest_state(str(order_id))
            if order is None:
                return {"status": "error", "message": f"Order {order_id} not found on chain."}
            order["orderStatus"] = new_status
            if additional_data:
                order.update(additional_data)
            entry = self._append(str(order_id), "UpdateOrder", str(caller_id or ""), order)
            logger.info("[LocalLedger] UpdateOrder %s -> %s", order_id, entry.tx_id)
            return self._success(entry)
        except Exception as e:
            logger.error("[LocalLedger] Update Error: %s", e)
            return {"status": "error", "message": str(e)}

    def get_order(self, order_id, caller_id=None):
        try:
            return filter_order_privacy(self._latest_state(str(order_id)), caller_id)
        except Exception as e:
            logger.error("[LocalLedger] get_order Error: %s", e)
            return None

    def get_all_orders(self, caller_id=None):
        from dashboard.models import LedgerEntry
        try:
            latest = {}
            for entry in LedgerEntry.objects.order_by("block_number").only("asset_id", "state"):
                latest[entry.asset_id] = entry.state
            return [filter_order_privacy(latest[k], caller_id) for k in sorted(latest)]
        except Exception as e:
            logger.error("[LocalLedger] get_all_orders Error: %s", e)
            return []

    def get_asset_history(self, order_id, caller_id=None):
        """
        Mesmo formato do GetOrderHistory do chaincode: mais recente primeiro, value em string JSON.
        Cada versão passa pelo filtro de sigilo conforme o caller_id (sem caller_id = consulta pública).
        """
        from dashboard.models import LedgerEntry
        try:
            entries = LedgerEntry.objects.filter(asset_id=str(order_id)).order_by("-block_number")
            return [{
                "txId": e.tx_id,
                "timestamp": _iso(e.timestamp),
                "isDelete": False,
                "value": _canonical(filter_order_privacy(e.state, caller_id)),
            } for e in entries]
        except Exception as e:
            logger.error("[LocalLedger] History Error: %s", e)
            return []

    # ------------------------------------------------------------------
    # Verificação de integridade
    # ------------------------------------------------------------------

    def verify_chain(self):
        """Recalcula todos os hashes. Devolve (ok, lista_de_problemas)."""
        from dashboard.models import LedgerEntry
        problems = []
        expected_prev = GENESIS_PREV_HASH
        expected_number = 0
        for e in LedgerEntry.objects.order_by("block_number").iterator():
            if e.block_number != expected_number:
                problems.append(f"Bloco #{e.block_number}: esperado #{expected_number} (bloco em falta).")
            if e.prev_hash != expected_prev:
                problems.append(f"Bloco #{e.block_number}: prev_hash não corresponde ao bloco anterior.")
            recomputed = compute_entry_hash(e.block_number, e.prev_hash, e.tx_id, e.asset_id,
                                            e.function, e.actor, e.timestamp, e.state)
            if recomputed != e.hash:
                problems.append(f"Bloco #{e.block_number} ({e.asset_id}): conteúdo alterado (hash inválido).")
            expected_prev = e.hash
            expected_number = e.block_number + 1
        return (not problems), problems
