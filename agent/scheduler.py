import asyncio
import logging
from datetime import datetime
from services.analytics_service import get_debtors_list
from services.rental_service import list_active_rentals
from database.db import get_db_connection
from config import BOT_TOKEN, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

async def run_overdue_and_expiry_check():
    """
    Avtomatlashtirilgan cron-skaner:
    1. Muddati kechikkan bo'lib to'lash to'lovlarini aniqlash va eslatma yozish
    2. 7 kun ichida muddati tugaydigan ijara (arenda) shartnomalarini aniqlash va bildirishnoma yaratish
    """
    logger.info("AI Skaner ishga tushdi: qarzdorlik va ijara muddatlarini tekshirish...")
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Qarzdorlar
    debtors = get_debtors_list()
    new_alerts = 0

    for d in debtors:
        # Oxirgi 24 soat ichida yuborilganini tekshirish (takrorlanmasligi uchun)
        cursor.execute("""
            SELECT id FROM notifications
            WHERE contract_id = ? AND notification_type = 'OVERDUE_ALERT'
              AND created_at >= datetime('now', '-1 day')
        """, (d["contract_id"],))
        if not cursor.fetchone():
            msg = (
                f"Hurmatli {d['customer_name']}! {d['car_model']} ({d.get('plate_number', '')}) "
                f"bo'yicha to'lovingiz {d['days_overdue']} kun kechikmoqda. Qarz: {int(d['total_debt_uzs']):,} so'm. "
                f"Iltimos, to'lovni zudlik bilan amalga oshiring."
            )
            cursor.execute("""
                INSERT INTO notifications (contract_id, customer_id, notification_type, recipient_phone, message, channel, status)
                VALUES (?, ?, 'OVERDUE_ALERT', ?, ?, 'TELEGRAM', 'PENDING')
            """, (d["contract_id"], d["customer_id"], d["customer_phone"], msg))
            new_alerts += 1

    # 2. Tugayotgan arendalar
    rentals = list_active_rentals()
    for r in rentals:
        if r.get("is_expiring_soon"):
            cursor.execute("""
                SELECT id FROM notifications
                WHERE contract_id = ? AND notification_type = 'RENTAL_EXPIRY_ALERT'
                  AND created_at >= datetime('now', '-3 days')
            """, (r["contract_id"],))
            if not cursor.fetchone():
                msg = (
                    f"Hurmatli {r['customer_name']}! {r['car_model']} ({r.get('plate_number', '')}) "
                    f"ijara shartnomangiz tugashiga {r['days_left']} kun qoldi. Shartnomani uzaytirish yoki mashinani topshirish uchun murojaat qiling."
                )
                cursor.execute("""
                    INSERT INTO notifications (contract_id, customer_id, notification_type, recipient_phone, message, channel, status)
                    VALUES (?, ?, 'RENTAL_EXPIRY_ALERT', ?, ?, 'SMS', 'PENDING')
                """, (r["contract_id"], r["customer_id"], r["customer_phone"], msg))
                new_alerts += 1

    conn.commit()
    conn.close()
    logger.info(f"AI Skaner yakunlandi: {new_alerts} ta yangi eslatma shakllantirildi.")
    return new_alerts
