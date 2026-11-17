"""
Views da aba "Stock Agent" (Produtor, Retalhista e Processador).

  GET  ai/stock-agent/status/     -> estado do Web Service + culturas com stock do utilizador
  POST ai/stock-agent/recommend/  -> {"culture_id": int, "mode": "lot"|"warehouse", "date": "YYYY-MM-DD"?}
"""
import datetime
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from dashboard.decorators import role_required
from dashboard.services import stock_agent_service

ALLOWED_ROLES = ['Producer', 'Retailer', 'Processor']


@login_required
@role_required(ALLOWED_ROLES)
@require_GET
def stock_agent_status(request):
    return JsonResponse({
        "online": stock_agent_service.check_health(),
        "perfil_tipo": stock_agent_service.user_role(request.user),
        "culturas": stock_agent_service.cultures_with_stock(request.user),
    })


@login_required
@role_required(ALLOWED_ROLES)
@require_POST
def stock_agent_recommend(request):
    try:
        body = json.loads(request.body or b"{}")
        culture_id = int(body.get("culture_id"))
    except (ValueError, TypeError):
        return JsonResponse({"status": "error", "message": "Pedido inválido: indique a cultura."}, status=400)
    mode = body.get("mode", "lot")
    today = None
    if body.get("date"):
        try:
            today = datetime.date.fromisoformat(body["date"])
        except ValueError:
            return JsonResponse({"status": "error", "message": "Data inválida."}, status=400)
    result = stock_agent_service.recommend(request.user, culture_id, mode, today)
    return JsonResponse(result, status=200 if result.get("status") == "success" else 422)
