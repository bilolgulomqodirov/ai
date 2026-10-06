import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from services.analytics_service import (
    get_revenue_breakdown,
    get_fleet_and_sales_metrics,
    get_debtors_list,
    build_executive_summary_data
)
from services.inventory_service import list_cars, get_car_by_id
from services.rental_service import list_active_rentals
from database.db import get_db_connection

def format_currency(amount: float) -> str:
    """Valyutani chiroyli formatda chiqarish"""
    return f"{int(amount):,} so'm".replace(",", " ")

# 1. OpenAI / Gemini Function Calling Tools Schemas
TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_monthly_revenue_report",
            "description": "Oylik umumiy tushumlar hisoboti: naqd sotuv, bo'lib to'lash (boshlang'ich to'lov va oylik yig'imlar) va ijara to'lovlarini alohida ko'rsatadi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "Yil (masalan: 2026). Agar berilmasa, joriy yil olinadi."
                    },
                    "month": {
                        "type": "integer",
                        "description": "Oy raqami (1-12). Agar berilmasa, joriy oy olinadi."
                    }
                },
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_debtors_report",
            "description": "To'lovni kechiktirgan qarzdorlar ro'yxatini chiqaradi (ijara va bo'lib to'lash qarzdorlari, kechikkan kunlar, jarimalar va telefon raqamlari).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_type": {
                        "type": "string",
                        "enum": ["ALL", "RENTAL", "INSTALLMENT"],
                        "description": "Qarzdorlik turi: ALL (barchasi), RENTAL (faqat ijara), INSTALLMENT (faqat bo'lib to'lash)."
                    }
                },
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_fleet_inventory_status",
            "description": "Avtomobillar inventarizatsiyasi holatini qaytaradi (sotuvda tayyor, arendaga berilgan, naqd sotilgan va muddatli to'lovdagi mashinalar soni).",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string",
                        "enum": ["ALL", "Available", "Rented", "Sold_Cash", "Sold_Installment"],
                        "description": "Qaysi holatdagi mashinalarni ko'rish kerak."
                    }
                },
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_car_and_contract_details",
            "description": "Mashina davlat raqami, VIN kod, model nomi yoki mijoz telefoni bo'yicha to'liq ma'lumot kartochkasi: kim minmoqda, qancha qarzi qoldi, keyingi to'lov sanasi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Mashina davlat raqami (masalan: 01 X 555 XX), VIN kodi, car_id yoki mijoz telefoni/ismi."
                    }
                },
                "required": ["identifier"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_executive_summary_report",
            "description": "Kompaniya rahbari uchun yuqori darajadagi tahliliy xulosa (Executive Summary): oylik daromad, avtopark rentabelligi, qarzdorlar tahlili va tavsiyalar.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_overdue_reminders",
            "description": "To'lovni kechiktirgan qarzdorlarga yoki ijara muddati tugayotgan mijozlarga avtomatik eslatma xabarnomalarini yuboradi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "Muayyan shartnoma ID si (ixtiyoriy, agar ko'rsatilmasa barcha qarzdorlarga yuboriladi)."
                    }
                },
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_available_cars",
            "description": "Sotuvda yoki arendada mavjud bo'lgan yangi mashinalarni model va byudjet bo'yicha qidirish.",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Mashina modeli (masalan: Cobalt, Tracker, Onix, Gentra, BYD)."
                    },
                    "max_budget_usd": {
                        "type": "number",
                        "description": "Maksimal byudjet AQSh dollarida."
                    }
                },
                "additionalProperties": False
            }
        }
    }
]

# 2. Asboblar implementatsiyasi (Tool Implementations)

def tool_get_monthly_revenue_report(year: Optional[int] = None, month: Optional[int] = None) -> str:
    data = get_revenue_breakdown(year, month)
    m = data["month_revenue"]
    a = data["all_time_revenue"]

    result = {
        "davr": data["period"],
        "naqd_sotuvdan_tushum": format_currency(m["cash_sales_uzs"]),
        "bolib_tolash_boshlangich": format_currency(m["installment_down_payments_uzs"]),
        "bolib_tolash_oylik_yigimlar": format_currency(m["installment_monthly_collections_uzs"]),
        "bolib_tolash_jami": format_currency(m["total_installment_revenue_uzs"]),
        "arenda_ijara_tushumi": format_currency(m["rental_collections_uzs"]),
        "boshqa_tushumlar": format_currency(m["other_collections_uzs"]),
        "joriy_oy_jami_tushumi": format_currency(m["total_month_revenue_uzs"]),
        "barcha_davrlar_jami_tushumi": format_currency(a["total_all_time_revenue_uzs"])
    }
    return json.dumps(result, ensure_ascii=False)

def tool_get_debtors_report(filter_type: str = "ALL") -> str:
    all_debtors = get_debtors_list()
    if filter_type == "RENTAL":
        debtors = [d for d in all_debtors if d["debt_type"] == "IJARA_ARENDA"]
    elif filter_type == "INSTALLMENT":
        debtors = [d for d in all_debtors if d["debt_type"] == "MUDDATLI_TOLOV"]
    else:
        debtors = all_debtors

    if not debtors:
        return json.dumps({
            "status": "clean",
            "message": "Ajoyib natija! Hozirda to'lov muddati o'tgan qarzdorlar mavjud emas."
        }, ensure_ascii=False)

    report = []
    total_debt = 0.0
    for d in debtors:
        total_debt += d["total_debt_uzs"]
        report.append({
            "mijoz": d["customer_name"],
            "telefon": d["customer_phone"],
            "avtomobil": f"{d['car_model']} ({d.get('plate_number', 'Raqamsiz')})",
            "shartnoma_id": d["contract_id"],
            "turi": "Ijara (Arenda)" if d["debt_type"] == "IJARA_ARENDA" else "Bo'lib to'lash",
            "kechikkan_oylar": d.get("overdue_months_count", 1),
            "kechikkan_kunlar": d.get("days_overdue", 0),
            "qarz_summasi": format_currency(d["total_debt_uzs"]),
            "jarima": format_currency(d.get("total_penalty_uzs", 0))
        })

    return json.dumps({
        "status": "debtors_found",
        "jami_qarzdorlar_soni": len(debtors),
        "jami_kechikkan_summa": format_currency(total_debt),
        "qarzdorlar": report
    }, ensure_ascii=False)

def tool_get_fleet_inventory_status(status_filter: str = "ALL") -> str:
    fleet = get_fleet_and_sales_metrics()
    cars = list_cars(status=status_filter if status_filter != "ALL" else None)

    summary = {
        "jami_mashinalar_soni": fleet["total_cars_in_system"],
        "salonda_tayyor_bosh": fleet["available_in_showroom"],
        "arendadagi_mashinalar": fleet["active_rentals_count"],
        "naqd_sotilganlar": fleet["sold_cash_count"],
        "bolib_tolashga_berilganlar": fleet["sold_installment_count"],
        "jami_sotilganlar": fleet["total_sold_cars"],
        "parkdan_foydalanish_foizi": f"{fleet['fleet_utilization_rate_pct']}%",
        "faol_kutilayotgan_haqlar_portfeli": format_currency(fleet["total_active_receivables_uzs"]),
        "namuna_mashinalar": [
            {
                "id": c["id"],
                "model": c["model"],
                "raqam": c.get("plate_number") or "Tranzit",
                "status": c["status"],
                "narx_usd": f"${c['sale_price_usd']:,}",
                "narx_uzs": format_currency(c["sale_price_uzs"])
            }
            for c in cars[:6]
        ]
    }
    return json.dumps(summary, ensure_ascii=False)

def tool_get_car_and_contract_details(identifier: str) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()

    clean_q = f"%{identifier.strip().lower()}%"

    # Avtomobilni VIN, raqam yoki model bo'yicha qidirish
    cursor.execute("""
        SELECT c.*, cust.full_name as customer_name, cust.phone as customer_phone,
               cust.address as customer_address,
               ctr.id as contract_id, ctr.contract_type, ctr.total_contract_uzs,
               ctr.down_payment_uzs, ctr.paid_amount_uzs, ctr.remaining_balance_uzs,
               ctr.monthly_payment_uzs, ctr.status as contract_status, ctr.term_months
        FROM cars c
        LEFT JOIN contracts ctr ON c.id = ctr.car_id AND ctr.status = 'ACTIVE'
        LEFT JOIN customers cust ON ctr.customer_id = cust.id
        WHERE LOWER(c.plate_number) LIKE ? 
           OR LOWER(c.vin) LIKE ? 
           OR LOWER(c.id) LIKE ? 
           OR LOWER(c.model) LIKE ?
           OR LOWER(cust.phone) LIKE ?
           OR LOWER(cust.full_name) LIKE ?
        ORDER BY ctr.created_at DESC LIMIT 1
    """, (clean_q, clean_q, clean_q, clean_q, clean_q, clean_q))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return json.dumps({
            "status": "not_found",
            "message": f"'{identifier}' bo'yicha ma'lumot topilmadi. Raqam yoki VIN kodni tekshiring."
        }, ensure_ascii=False)

    data = dict(row)
    res = {
        "status": "found",
        "mashina_id": data["id"],
        "model": data["model"],
        "vin": data["vin"],
        "davlat_raqami": data["plate_number"] or "Biriktirilmagan",
        "ishlab_chiqarilgan_yili": data["year"],
        "holati": data["status"],
        "umumiy_narxi": format_currency(data["sale_price_uzs"]),
        "oylik_ijara_narxi": format_currency(data["rental_price_monthly_uzs"])
    }

    if data.get("contract_id"):
        res["amaldagi_shartnoma"] = {
            "shartnoma_id": data["contract_id"],
            "turi": data["contract_type"],
            "mijoz_ismi": data["customer_name"],
            "mijoz_telefoni": data["customer_phone"],
            "shartnoma_summasi": format_currency(data["total_contract_uzs"]),
            "boshlangich_tolov": format_currency(data["down_payment_uzs"]),
            "jami_tolangan": format_currency(data["paid_amount_uzs"]),
            "qoldiq_qarz": format_currency(data["remaining_balance_uzs"]),
            "oylik_tolov": format_currency(data["monthly_payment_uzs"]),
            "shartnoma_holati": data["contract_status"]
        }
    else:
        res["amaldagi_shartnoma"] = "Hozirda avtomobil bo'sh (salonda sotuvda yoki arendaga tayyor)."

    return json.dumps(res, ensure_ascii=False)

def tool_generate_executive_summary_report() -> str:
    data = build_executive_summary_data()
    kpi = data["kpi_overview"]
    rev = data["revenue_breakdown"]

    summary = {
        "sana": data["generated_at"],
        "joriy_oy_tushumi": format_currency(kpi["total_monthly_revenue_uzs"]),
        "barcha_davrlar_tushumi": format_currency(kpi["total_all_time_revenue_uzs"]),
        "jami_sotilgan_mashinalar": kpi["total_sold_cars"],
        "faol_arendadagi_mashinalar": kpi["active_rentals_count"],
        "salondagi_bosh_mashinalar": kpi["available_cars_count"],
        "avtopark_samaradorligi": f"{kpi['fleet_utilization_pct']}%",
        "faol_kutilayotgan_portfel": format_currency(kpi["total_active_receivables_uzs"]),
        "qarzdorlar_soni": kpi["total_debtors_count"],
        "xavfli_kechikkan_qarz_summasi": format_currency(kpi["total_overdue_debt_uzs"]),
        "oylik_tushum_tarkibi": {
            "naqd_sotuv": format_currency(rev["cash_sales_uzs"]),
            "bolib_tolash_boshlangich": format_currency(rev["installment_down_payments_uzs"]),
            "bolib_tolash_oylik": format_currency(rev["installment_monthly_collections_uzs"]),
            "ijara_tushumi": format_currency(rev["rental_collections_uzs"])
        },
        "strategik_tavsiyalar": [
            f"Kechikkan qarzlar summasi {format_currency(kpi['total_overdue_debt_uzs'])} ga yetdi. Qarzdorlarga zudlik bilan avtomatik bildirishnoma jo'nating.",
            f"Salonda {kpi['available_cars_count']} ta bo'sh mashina mavjud. Ularni sotuvga yoki arendaga tezroq chiqarish tavsiya etiladi.",
            f"Avtoparkdan foydalanish samaradorligi {kpi['fleet_utilization_pct']}%. Bu ko'rsatkichni 75% ga yetkazish uchun yangi mijozlar arizasini faollashtiring."
        ]
    }
    return json.dumps(summary, ensure_ascii=False)

def tool_trigger_overdue_reminders(contract_id: Optional[str] = None) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()

    debtors = get_debtors_list()
    if contract_id:
        debtors = [d for d in debtors if d["contract_id"] == contract_id]

    created_alerts = []
    for d in debtors:
        msg = (
            f"Hurmatli {d['customer_name']}! Sizning {d['car_model']} ({d.get('plate_number', '')}) "
            f"bo'yicha to'lovingiz kechikmoqda. Qarz summasi: {format_currency(d['total_debt_uzs'])}. "
            f"Iltimos, Click, Payme yoki bank orqali to'lovni zudlik bilan amalga oshiring."
        )
        cursor.execute("""
            INSERT INTO notifications (contract_id, customer_id, notification_type, recipient_phone, message, channel, status)
            VALUES (?, ?, 'OVERDUE_ALERT', ?, ?, 'TELEGRAM', 'SENT')
        """, (d["contract_id"], d["customer_id"], d["customer_phone"], msg))
        created_alerts.append({
            "mijoz": d["customer_name"],
            "telefon": d["customer_phone"],
            "summa": format_currency(d["total_debt_uzs"]),
            "status": "Yuborildi (SENT)"
        })

    conn.commit()
    conn.close()

    return json.dumps({
        "status": "success",
        "yuborilgan_bildirishnomalar_soni": len(created_alerts),
        "tafsilotlar": created_alerts
    }, ensure_ascii=False)

def tool_search_available_cars(model: str = "", max_budget_usd: float = 0.0) -> str:
    cars = list_cars(status="Available", search=model if model else None)
    if max_budget_usd > 0:
        cars = [c for c in cars if c["sale_price_usd"] <= max_budget_usd]

    if not cars:
        return json.dumps({
            "status": "not_found",
            "message": "Afsuski, so'rovingizga mos bo'sh avtomobil topilmadi."
        }, ensure_ascii=False)

    return json.dumps({
        "status": "success",
        "topilgan_mashinalar_soni": len(cars),
        "mashinalar": [
            {
                "id": c["id"],
                "model": c["model"],
                "yil": c["year"],
                "narx_usd": f"${c['sale_price_usd']:,}",
                "narx_uzs": format_currency(c["sale_price_uzs"]),
                "oylik_ijara_uzs": format_currency(c["rental_price_monthly_uzs"]),
                "yoqilgi": c["fuel_type"],
                "uzatish": c["transmission"],
                "tavsif": c.get("description", "")
            }
            for c in cars
        ]
    }, ensure_ascii=False)

def execute_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Asboblar dispetcheri"""
    try:
        if tool_name == "get_monthly_revenue_report":
            return tool_get_monthly_revenue_report(arguments.get("year"), arguments.get("month"))
        elif tool_name == "get_debtors_report":
            return tool_get_debtors_report(arguments.get("filter_type", "ALL"))
        elif tool_name == "get_fleet_inventory_status":
            return tool_get_fleet_inventory_status(arguments.get("status_filter", "ALL"))
        elif tool_name == "get_car_and_contract_details":
            return tool_get_car_and_contract_details(arguments.get("identifier", ""))
        elif tool_name == "generate_executive_summary_report":
            return tool_generate_executive_summary_report()
        elif tool_name == "trigger_overdue_reminders":
            return tool_trigger_overdue_reminders(arguments.get("contract_id"))
        elif tool_name == "search_available_cars":
            return tool_search_available_cars(arguments.get("model", ""), arguments.get("max_budget_usd", 0.0))
        else:
            return json.dumps({"error": f"Noma'lum asbob: {tool_name}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Asbob bajarishda xatolik: {str(e)}"}, ensure_ascii=False)
