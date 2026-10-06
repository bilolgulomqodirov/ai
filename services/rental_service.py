import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from database.db import get_db_connection
from database.models import RentalRequest
from services.sales_service import get_or_create_customer

def execute_rental(req: RentalRequest) -> Dict[str, Any]:
    """Mashinani ijaraga (arenda) berish tranzaksiyasi"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cars WHERE id = ?", (req.car_id,))
    car = cursor.fetchone()
    if not car:
        conn.close()
        raise ValueError(f"Mashina topilmadi: {req.car_id}")
    if car["status"] != "Available":
        conn.close()
        raise ValueError(f"Ushbu mashina arendaga berish uchun bo'sh emas. Joriy holati: {car['status']}")

    customer_id = get_or_create_customer(cursor, req.customer)

    monthly_rate = req.monthly_rate_uzs or car["rental_price_monthly_uzs"]
    term_months = req.term_months or 1
    total_contract = monthly_rate * term_months

    contract_id = f"CTR-RENT-{datetime.now().strftime('%Y%m')}-{str(uuid.uuid4())[:4].upper()}"
    start_date = datetime.now()
    end_date = start_date + timedelta(days=term_months * 30)

    # 1. Ijara shartnomasini kiritish (Dastlab 1-oy to'lovi olinadi)
    initial_payment = monthly_rate + req.deposit_uzs
    cursor.execute("""
        INSERT INTO contracts (
            id, contract_type, car_id, customer_id, start_date, end_date,
            total_contract_uzs, down_payment_uzs, paid_amount_uzs, remaining_balance_uzs,
            monthly_payment_uzs, term_months, billing_day, status, notes
        ) VALUES (?, 'RENTAL', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
    """, (
        contract_id, req.car_id, customer_id,
        start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"),
        total_contract, req.deposit_uzs, monthly_rate, max(0.0, total_contract - monthly_rate),
        monthly_rate, term_months, start_date.day, req.notes
    ))

    # 2. Mashina statusini Rented ga o'tkazish
    cursor.execute("UPDATE cars SET status = 'Rented' WHERE id = ?", (req.car_id,))

    # 3. Tranzaksiya yozish (1-oy ijara to'lovi)
    txn_code = f"TXN-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    cursor.execute("""
        INSERT INTO transactions (
            transaction_code, contract_id, customer_id, car_id, schedule_id,
            payment_category, amount_uzs, payment_method, payment_date, reference_no, notes
        ) VALUES (?, ?, ?, ?, NULL, 'RENTAL_MONTHLY', ?, ?, CURRENT_TIMESTAMP, ?, '1-oy ijara to''lovi')
    """, (txn_code, contract_id, customer_id, req.car_id, monthly_rate, req.payment_method, f"RENT-{req.car_id}"))

    # Agar depozit bo'lsa
    if req.deposit_uzs > 0:
        dep_code = f"TXN-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
        cursor.execute("""
            INSERT INTO transactions (
                transaction_code, contract_id, customer_id, car_id, schedule_id,
                payment_category, amount_uzs, payment_method, payment_date, reference_no, notes
            ) VALUES (?, ?, ?, ?, NULL, 'SECURITY_DEPOSIT', ?, ?, CURRENT_TIMESTAMP, ?, 'Ijara depoziti')
        """, (dep_code, contract_id, customer_id, req.car_id, req.deposit_uzs, req.payment_method, f"DEP-{req.car_id}"))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "contract_id": contract_id,
        "car_model": car["model"],
        "vin": car["vin"],
        "plate_number": car["plate_number"],
        "customer_name": req.customer.full_name,
        "term_months": term_months,
        "monthly_rate_uzs": monthly_rate,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "message": f"{car['model']} {term_months} oy muddatga ijaraga topshirildi."
    }

def list_active_rentals() -> List[Dict[str, Any]]:
    """Amaldagi barcha ijara shartnomalarini olish va muddati qolganligini hisoblash"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            c.id as contract_id,
            c.start_date,
            c.end_date,
            c.monthly_payment_uzs,
            c.total_contract_uzs,
            c.paid_amount_uzs,
            c.remaining_balance_uzs,
            c.billing_day,
            c.status as contract_status,
            cust.id as customer_id,
            cust.full_name as customer_name,
            cust.phone as customer_phone,
            car.id as car_id,
            car.model as car_model,
            car.plate_number,
            car.vin,
            car.image_url
        FROM contracts c
        JOIN customers cust ON c.customer_id = cust.id
        JOIN cars car ON c.car_id = car.id
        WHERE c.contract_type = 'RENTAL' AND c.status = 'ACTIVE'
        ORDER BY c.end_date ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    now = datetime.now()
    rentals = []
    for r in rows:
        item = dict(r)
        try:
            end_dt = datetime.strptime(item["end_date"], "%Y-%m-%d")
            days_left = (end_dt - now).days
        except Exception:
            days_left = 0

        item["days_left"] = days_left
        item["is_expiring_soon"] = 0 <= days_left <= 7
        item["is_expired"] = days_left < 0
        rentals.append(item)

    return rentals
