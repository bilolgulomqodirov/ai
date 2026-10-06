import sqlite3
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from database.db import get_db_connection
from database.models import PaymentRecordRequest

def record_payment_and_get_details(req: PaymentRecordRequest) -> Dict[str, Any]:
    """
    To'lovni qabul qilish va tranzaksiya qayd etilgach, avtomobil,
    mijoz va shartnoma bo'yicha to'liq ma'lumotlar kartochkasini shakllantirib qaytarish.
    (Talab 4: Tranzaksiyalar va Ma'lumot integratsiyasi)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Shartnomani topish
    cursor.execute("""
        SELECT c.*, cust.full_name as customer_name, cust.phone as customer_phone,
               cust.passport_series, cust.pinfl, cust.address as customer_address,
               car.model as car_model, car.make, car.year as car_year, car.vin,
               car.plate_number, car.color, car.mileage, car.status as car_status,
               car.image_url
        FROM contracts c
        JOIN customers cust ON c.customer_id = cust.id
        JOIN cars car ON c.car_id = car.id
        WHERE c.id = ?
    """, (req.contract_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Shartnoma topilmadi: {req.contract_id}")

    contract_info = dict(row)
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # 2. To'lov turiga qarab grafikni yangilash
    matched_schedule_id = req.schedule_id
    category = req.payment_category

    if contract_info["contract_type"] == "SALE_INSTALLMENT":
        if not category:
            category = "INSTALLMENT_MONTHLY"

        # Agar schedule_id ko'rsatilmagan bo'lsa, eng birinchi to'lanmagan (OVERDUE yoki PENDING) oyni olamiz
        if not matched_schedule_id:
            cursor.execute("""
                SELECT id, installment_no, amount_due_uzs FROM installment_schedules
                WHERE contract_id = ? AND status IN ('OVERDUE', 'PENDING')
                ORDER BY installment_no ASC LIMIT 1
            """, (req.contract_id,))
            next_sched = cursor.fetchone()
            if next_sched:
                matched_schedule_id = next_sched["id"]

        if matched_schedule_id:
            cursor.execute("""
                UPDATE installment_schedules
                SET status = 'PAID', amount_paid_uzs = amount_due_uzs, paid_at = ?
                WHERE id = ?
            """, (now_str, matched_schedule_id))

    elif contract_info["contract_type"] == "RENTAL":
        if not category:
            category = "RENTAL_MONTHLY"
    else:
        if not category:
            category = "CASH_SALE"

    # 3. Shartnoma balansini yangilash
    new_paid = contract_info["paid_amount_uzs"] + req.amount_uzs
    new_balance = max(0.0, contract_info["remaining_balance_uzs"] - req.amount_uzs)
    new_contract_status = contract_info["status"]
    if new_balance == 0.0 and contract_info["contract_type"] in ("SALE_INSTALLMENT", "SALE_CASH"):
        new_contract_status = "COMPLETED"

    cursor.execute("""
        UPDATE contracts
        SET paid_amount_uzs = ?, remaining_balance_uzs = ?, status = ?
        WHERE id = ?
    """, (new_paid, new_balance, new_contract_status, req.contract_id))

    # 4. Tranzaksiya yozuvini kiritish
    txn_code = f"TXN-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    cursor.execute("""
        INSERT INTO transactions (
            transaction_code, contract_id, customer_id, car_id, schedule_id,
            payment_category, amount_uzs, payment_method, payment_date, reference_no, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        txn_code, req.contract_id, contract_info["customer_id"], contract_info["car_id"],
        matched_schedule_id, category, req.amount_uzs, req.payment_method,
        now_str, req.reference_no or f"REF-{txn_code}", req.notes or f"To'lov qabul qilindi"
    ))

    # 5. Ekranda to'liq avtomobil va mijoz ma'lumotlarini shakllantirish
    # Oylik to'lovlar jadvalidan navbatdagi to'lovni aniqlash
    cursor.execute("""
        SELECT due_date, amount_due_uzs, installment_no FROM installment_schedules
        WHERE contract_id = ? AND status IN ('OVERDUE', 'PENDING')
        ORDER BY installment_no ASC LIMIT 1
    """, (req.contract_id,))
    next_due_row = cursor.fetchone()

    # To'langan oylar soni
    cursor.execute("""
        SELECT COUNT(*) FROM installment_schedules
        WHERE contract_id = ? AND status = 'PAID'
    """, (req.contract_id,))
    paid_months_count = cursor.fetchone()[0]

    # Qolgan muddati o'tgan (overdue) summa
    cursor.execute("""
        SELECT COALESCE(SUM(amount_due_uzs - amount_paid_uzs), 0) FROM installment_schedules
        WHERE contract_id = ? AND status = 'OVERDUE'
    """, (req.contract_id,))
    total_overdue = cursor.fetchone()[0]

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": "To'lov muvaffaqiyatli qabul qilindi va hisob-kitob yangilandi.",
        "transaction": {
            "transaction_code": txn_code,
            "amount_uzs": req.amount_uzs,
            "payment_method": req.payment_method,
            "payment_category": category,
            "payment_date": now_str,
            "reference_no": req.reference_no or txn_code
        },
        "vehicle_and_customer_details": {
            "car_id": contract_info["car_id"],
            "model": contract_info["car_model"],
            "make": contract_info["make"],
            "year": contract_info["car_year"],
            "vin": contract_info["vin"],
            "plate_number": contract_info["plate_number"],
            "color": contract_info["color"],
            "mileage": contract_info["mileage"],
            "image_url": contract_info["image_url"],
            "car_status": contract_info["car_status"],
            "customer_name": contract_info["customer_name"],
            "customer_phone": contract_info["customer_phone"],
            "customer_passport": contract_info["passport_series"],
            "customer_pinfl": contract_info["pinfl"],
            "customer_address": contract_info["customer_address"],
            "contract_id": contract_info["id"],
            "contract_type": contract_info["contract_type"],
            "total_contract_uzs": contract_info["total_contract_uzs"],
            "down_payment_uzs": contract_info["down_payment_uzs"],
            "total_paid_uzs": new_paid,
            "remaining_debt_uzs": new_balance,
            "monthly_payment_uzs": contract_info["monthly_payment_uzs"],
            "paid_installments_count": paid_months_count,
            "total_installments": contract_info["term_months"],
            "next_payment_due_date": next_due_row["due_date"] if next_due_row else "Yakunlangan",
            "next_payment_amount_uzs": next_due_row["amount_due_uzs"] if next_due_row else 0,
            "current_overdue_debt_uzs": total_overdue
        }
    }

def get_transactions_ledger(limit: int = 100) -> List[Dict[str, Any]]:
    """Barcha to'lovlar jurnali (avtomobil va mijoz ma'lumotlari bilan)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            t.*,
            c.contract_type,
            c.remaining_balance_uzs,
            car.model as car_model,
            car.plate_number,
            car.vin,
            cust.full_name as customer_name,
            cust.phone as customer_phone
        FROM transactions t
        JOIN contracts c ON t.contract_id = c.id
        JOIN customers cust ON t.customer_id = cust.id
        JOIN cars car ON t.car_id = car.id
        ORDER BY t.payment_date DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
