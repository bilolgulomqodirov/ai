import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from database.db import get_db_connection
from database.models import CashSaleRequest, InstallmentSaleRequest, CustomerInput

def get_or_create_customer(cursor: sqlite3.Cursor, customer_in: CustomerInput) -> int:
    """Mavjud mijozni telefon orqali topish yoki yangisini yaratish"""
    phone = customer_in.phone.strip()
    cursor.execute("SELECT id FROM customers WHERE phone = ?", (phone,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute("""
        INSERT INTO customers (full_name, phone, passport_series, pinfl, address)
        VALUES (?, ?, ?, ?, ?)
    """, (customer_in.full_name, phone, customer_in.passport_series, customer_in.pinfl, customer_in.address))
    return cursor.lastrowid

def execute_cash_sale(req: CashSaleRequest) -> Dict[str, Any]:
    """Naqd pulga sotish tranzaksiyasi: to'liq to'lov, mashina statusi Sold_Cash bo'ladi"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Mashinani tekshirish
    cursor.execute("SELECT * FROM cars WHERE id = ?", (req.car_id,))
    car = cursor.fetchone()
    if not car:
        conn.close()
        raise ValueError(f"Mashina topilmadi: {req.car_id}")
    if car["status"] != "Available":
        conn.close()
        raise ValueError(f"Ushbu mashina sotuvda emas. Joriy holati: {car['status']}")

    customer_id = get_or_create_customer(cursor, req.customer)

    # Narxni aniqlash
    sale_amount = req.actual_sale_price_uzs or car["sale_price_uzs"]
    contract_id = f"CTR-CASH-{datetime.now().strftime('%Y%m')}-{str(uuid.uuid4())[:4].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d")

    # 2. Shartnoma yaratish (To'liq yopilgan, COMPLETED)
    cursor.execute("""
        INSERT INTO contracts (
            id, contract_type, car_id, customer_id, start_date, end_date,
            total_contract_uzs, down_payment_uzs, paid_amount_uzs, remaining_balance_uzs,
            monthly_payment_uzs, term_months, billing_day, status, notes
        ) VALUES (?, 'SALE_CASH', ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 1, 'COMPLETED', ?)
    """, (contract_id, req.car_id, customer_id, now_str, now_str, sale_amount, sale_amount, sale_amount, req.notes))

    # 3. Mashina statusini Sold_Cash ga o'tkazish
    cursor.execute("UPDATE cars SET status = 'Sold_Cash' WHERE id = ?", (req.car_id,))

    # 4. Tranzaksiyani yozish
    txn_code = f"TXN-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    cursor.execute("""
        INSERT INTO transactions (
            transaction_code, contract_id, customer_id, car_id, schedule_id,
            payment_category, amount_uzs, payment_method, payment_date, reference_no, notes
        ) VALUES (?, ?, ?, ?, NULL, 'CASH_SALE', ?, ?, CURRENT_TIMESTAMP, ?, ?)
    """, (txn_code, contract_id, customer_id, req.car_id, sale_amount, req.payment_method, f"CASH-{req.car_id}", req.notes))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "contract_id": contract_id,
        "transaction_code": txn_code,
        "car_model": car["model"],
        "vin": car["vin"],
        "plate_number": car["plate_number"],
        "customer_name": req.customer.full_name,
        "amount_paid_uzs": sale_amount,
        "message": f"{car['model']} naqd to'lov bilan muvaffaqiyatli sotildi."
    }

def execute_installment_sale(req: InstallmentSaleRequest) -> Dict[str, Any]:
    """Bo'lib to'lashga sotish: Boshlang'ich to'lov, foiz ustama va oylik grafik yaratish"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cars WHERE id = ?", (req.car_id,))
    car = cursor.fetchone()
    if not car:
        conn.close()
        raise ValueError(f"Mashina topilmadi: {req.car_id}")
    if car["status"] != "Available":
        conn.close()
        raise ValueError(f"Ushbu mashina sotuvda emas. Joriy holati: {car['status']}")

    base_price = car["sale_price_uzs"]
    down_payment = req.down_payment_uzs

    if down_payment >= base_price:
        conn.close()
        raise ValueError("Boshlang'ich to'lov umumiy narxdan katta yoki teng bo'lishi mumkin emas. Naqd sotuvdan foydalaning.")

    customer_id = get_or_create_customer(cursor, req.customer)

    # Foiz va oylik hisob-kitob
    financed_amount = base_price - down_payment
    term_years = req.term_months / 12.0
    markup_amount = financed_amount * (req.annual_markup_percent / 100.0) * term_years
    total_remaining_with_markup = financed_amount + markup_amount
    monthly_payment = round(total_remaining_with_markup / req.term_months)
    total_contract_uzs = down_payment + (monthly_payment * req.term_months)

    contract_id = f"CTR-INST-{datetime.now().strftime('%Y%m')}-{str(uuid.uuid4())[:4].upper()}"
    start_date = datetime.now()
    end_date = start_date + timedelta(days=req.term_months * 30)

    # 1. Shartnomani saqlash
    cursor.execute("""
        INSERT INTO contracts (
            id, contract_type, car_id, customer_id, start_date, end_date,
            total_contract_uzs, down_payment_uzs, paid_amount_uzs, remaining_balance_uzs,
            monthly_payment_uzs, term_months, billing_day, status, notes
        ) VALUES (?, 'SALE_INSTALLMENT', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
    """, (
        contract_id, req.car_id, customer_id,
        start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"),
        total_contract_uzs, down_payment, down_payment, total_remaining_with_markup,
        monthly_payment, req.term_months, start_date.day, req.notes
    ))

    # 2. Mashina statusini Sold_Installment ga o'tkazish
    cursor.execute("UPDATE cars SET status = 'Sold_Installment' WHERE id = ?", (req.car_id,))

    # 3. Boshlang'ich to'lov tranzaksiyasini yozish
    txn_code = f"TXN-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    cursor.execute("""
        INSERT INTO transactions (
            transaction_code, contract_id, customer_id, car_id, schedule_id,
            payment_category, amount_uzs, payment_method, payment_date, reference_no, notes
        ) VALUES (?, ?, ?, ?, NULL, 'DOWN_PAYMENT', ?, ?, CURRENT_TIMESTAMP, ?, 'Boshlang''ich to''lov')
    """, (txn_code, contract_id, customer_id, req.car_id, down_payment, req.payment_method, f"DOWN-{req.car_id}"))

    # 4. Oylik to'lovlar jadvalini (Installment Schedules) generatsiya qilish
    schedules = []
    for month in range(1, req.term_months + 1):
        due_date = (start_date + timedelta(days=month * 30)).strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO installment_schedules (
                contract_id, installment_no, due_date, amount_due_uzs,
                amount_paid_uzs, status, paid_at, penalty_uzs, notes
            ) VALUES (?, ?, ?, ?, 0, 'PENDING', NULL, 0, ?)
        """, (contract_id, month, due_date, monthly_payment, f"{month}-oylik to'lov"))
        schedules.append({
            "installment_no": month,
            "due_date": due_date,
            "amount_due_uzs": monthly_payment,
            "status": "PENDING"
        })

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "contract_id": contract_id,
        "car_model": car["model"],
        "vin": car["vin"],
        "plate_number": car["plate_number"],
        "customer_name": req.customer.full_name,
        "down_payment_uzs": down_payment,
        "term_months": req.term_months,
        "monthly_payment_uzs": monthly_payment,
        "total_contract_uzs": total_contract_uzs,
        "remaining_balance_uzs": total_remaining_with_markup,
        "schedules_count": len(schedules),
        "message": f"{car['model']} {req.term_months} oylik bo'lib to'lashga muvaffaqiyatli rasmiylashtirildi."
    }

def get_contract_schedule(contract_id: str) -> List[Dict[str, Any]]:
    """Shartnoma bo'yicha oylik grafik holati (Paid, Pending, Overdue)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM installment_schedules
        WHERE contract_id = ?
        ORDER BY installment_no ASC
    """, (contract_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
