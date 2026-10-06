import sqlite3
import uuid
from typing import List, Dict, Any, Optional
from database.db import get_db_connection
from database.models import CarCreate

def list_cars(status: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Avtomobillar ro'yxatini holati va qidiruv bo'yicha olish"""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM cars WHERE 1=1"
    params = []

    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status)

    if search:
        query += " AND (LOWER(model) LIKE ? OR LOWER(vin) LIKE ? OR LOWER(plate_number) LIKE ?)"
        s = f"%{search.lower()}%"
        params.extend([s, s, s])

    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_car_by_id(car_id: str) -> Optional[Dict[str, Any]]:
    """Mashina ID bo'yicha to'liq ma'lumot va faol shartnomasi (agar bo'lsa)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cars WHERE id = ?", (car_id,))
    car_row = cursor.fetchone()
    if not car_row:
        conn.close()
        return None

    car = dict(car_row)

    # Agar mashina Rented yoki Sold_Installment bo'lsa, amaldagi shartnoma va mijozni ulaymiz
    cursor.execute("""
        SELECT c.*, cust.full_name as customer_name, cust.phone as customer_phone
        FROM contracts c
        JOIN customers cust ON c.customer_id = cust.id
        WHERE c.car_id = ? AND c.status = 'ACTIVE'
        ORDER BY c.created_at DESC LIMIT 1
    """, (car_id,))
    contract_row = cursor.fetchone()
    if contract_row:
        car["active_contract"] = dict(contract_row)
    else:
        car["active_contract"] = None

    conn.close()
    return car

def add_car(car_data: CarCreate) -> Dict[str, Any]:
    """Yangi avtomobil qo'shish"""
    conn = get_db_connection()
    cursor = conn.cursor()

    car_id = car_data.id or f"CAR-{str(uuid.uuid4())[:6].upper()}"

    cursor.execute("""
        INSERT INTO cars (
            id, model, make, year, vin, plate_number, color, mileage,
            fuel_type, transmission, purchase_price_usd, sale_price_usd,
            sale_price_uzs, rental_price_daily_usd, rental_price_monthly_usd,
            rental_price_monthly_uzs, status, condition, image_url, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        car_id, car_data.model, car_data.make, car_data.year, car_data.vin,
        car_data.plate_number, car_data.color, car_data.mileage,
        car_data.fuel_type, car_data.transmission, car_data.purchase_price_usd,
        car_data.sale_price_usd, car_data.sale_price_uzs, car_data.rental_price_daily_usd,
        car_data.rental_price_monthly_usd, car_data.rental_price_monthly_uzs,
        "Available", car_data.condition, car_data.image_url, car_data.description
    ))
    conn.commit()
    conn.close()
    return get_car_by_id(car_id)

def update_car_status(car_id: str, new_status: str) -> bool:
    """Mashina statusini yangilash"""
    valid_statuses = ('Available', 'Rented', 'Sold_Cash', 'Sold_Installment')
    if new_status not in valid_statuses:
        raise ValueError(f"Noto'g'ri status. Ruxsat etilgan: {valid_statuses}")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE cars SET status = ? WHERE id = ?", (new_status, car_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0
