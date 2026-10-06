from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any

from database.models import (
    CarCreate,
    CashSaleRequest,
    InstallmentSaleRequest,
    RentalRequest,
    PaymentRecordRequest,
    AIChatRequest
)
from services.inventory_service import (
    list_cars,
    get_car_by_id,
    add_car,
    update_car_status
)
from services.sales_service import (
    execute_cash_sale,
    execute_installment_sale,
    get_contract_schedule
)
from services.rental_service import (
    execute_rental,
    list_active_rentals
)
from services.transaction_service import (
    record_payment_and_get_details,
    get_transactions_ledger
)
from services.analytics_service import (
    get_revenue_breakdown,
    get_fleet_and_sales_metrics,
    get_debtors_list,
    build_executive_summary_data
)
from agent.agent_runner import agent_instance
from agent.tools import tool_trigger_overdue_reminders

router = APIRouter(prefix="/api")

# ==================== 1. CAR INVENTORY ====================

@router.get("/cars", summary="Barcha avtomobillar ro'yxati (filtrlash bilan)")
def api_list_cars(
    status: Optional[str] = Query(None, description="Available, Rented, Sold_Cash, Sold_Installment, ALL"),
    search: Optional[str] = Query(None, description="Model, VIN yoki davlat raqami")
):
    try:
        return list_cars(status=status, search=search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cars/{car_id}", summary="Mashina to'liq ma'lumoti va amaldagi shartnomasi")
def api_get_car(car_id: str):
    car = get_car_by_id(car_id)
    if not car:
        raise HTTPException(status_code=404, detail="Avtomobil topilmadi")
    return car

@router.post("/cars", summary="Yangi avtomobil qo'shish")
def api_add_car(car: CarCreate):
    try:
        return add_car(car)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/cars/{car_id}/status", summary="Mashina holatini yangilash")
def api_update_car_status(car_id: str, new_status: str):
    try:
        ok = update_car_status(car_id, new_status)
        if not ok:
            raise HTTPException(status_code=404, detail="Mashina topilmadi")
        return {"status": "success", "car_id": car_id, "new_status": new_status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== 2. SALES MANAGEMENT ====================

@router.post("/sales/cash", summary="Naqd pulga sotish (To'liq to'lov, mashina Sold_Cash bo'ladi)")
def api_cash_sale(req: CashSaleRequest):
    try:
        return execute_cash_sale(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/sales/installment", summary="Bo'lib to'lashga sotish (Grafik shakllanadi, mashina Sold_Installment bo'ladi)")
def api_installment_sale(req: InstallmentSaleRequest):
    try:
        return execute_installment_sale(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/sales/contracts/{contract_id}/schedule", summary="Shartnomaning oylik to'lovlar jadvali (Paid/Pending/Overdue)")
def api_get_schedule(contract_id: str):
    try:
        return get_contract_schedule(contract_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== 3. RENTAL MANAGEMENT ====================

@router.post("/rentals", summary="Mashinani ijaraga (arenda) berish")
def api_create_rental(req: RentalRequest):
    try:
        return execute_rental(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/rentals/active", summary="Faol ijaradagi mashinalar va muddatlari")
def api_active_rentals():
    try:
        return list_active_rentals()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 4. TRANSACTIONS & DETAILS ====================

@router.post("/payments", summary="To'lov qabul qilish va avtomobilning to'liq ma'lumotlar kartochkasini olish")
def api_record_payment(req: PaymentRecordRequest):
    try:
        # Talab 4: To'lov amalga oshirilganda ekranda mashina haqidagi to'liq ma'lumotlar avtomatik shakllanadi
        return record_payment_and_get_details(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/payments/ledger", summary="Barcha to'lovlar va tranzaksiyalar jurnali")
def api_get_ledger(limit: int = 50):
    try:
        return get_transactions_ledger(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 5. REPORTING & ANALYTICS ====================

@router.get("/analytics/monthly-revenue", summary="Oylik tushumlar (Naqd, Bo'lib to'lash va Ijara)")
def api_monthly_revenue(year: Optional[int] = None, month: Optional[int] = None):
    try:
        return get_revenue_breakdown(year=year, month=month)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/fleet", summary="Avtopark va sotuv ko'rsatkichlari")
def api_fleet_metrics():
    try:
        return get_fleet_and_sales_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/debtors", summary="To'lovni kechiktirgan qarzdorlar ro'yxati")
def api_debtors():
    try:
        return get_debtors_list()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/executive-summary", summary="Rahbariyat uchun Executive Summary tahliliy ma'lumotlari")
def api_executive_summary():
    try:
        return build_executive_summary_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 6. AI AGENT CO-PILOT ====================

@router.post("/ai/chat", summary="AI Agent bilan muloqot (Savol-javob, hisobotlar, ma'lumot qidiruv)")
async def api_ai_chat(req: AIChatRequest):
    try:
        result = await agent_instance.process_message(req.message, session_id=req.session_id or "default")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ai/check-reminders", summary="Qarzdorlarga avtomatik eslatma xabarlarini yuborish")
def api_trigger_reminders(contract_id: Optional[str] = None):
    try:
        import json
        raw = tool_trigger_overdue_reminders(contract_id)
        return json.loads(raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
