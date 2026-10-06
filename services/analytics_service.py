import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from database.db import get_db_connection

def get_revenue_breakdown(year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
    """
    Oylik va umumiy tushumlar hisoboti:
    - Naqd sotuv (CASH_SALE)
    - Bo'lib to'lash boshlang'ich to'lov (DOWN_PAYMENT)
    - Bo'lib to'lash oylik yig'imlari (INSTALLMENT_MONTHLY)
    - Ijara to'lovlari (RENTAL_MONTHLY)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now()
    target_year = year or now.year
    target_month = month or now.month
    month_prefix = f"{target_year:04d}-{target_month:02d}"

    # 1. Joriy oy bo'yicha tushumlar
    cursor.execute("""
        SELECT 
            payment_category,
            COALESCE(SUM(amount_uzs), 0) as total_uzs,
            COUNT(*) as txn_count
        FROM transactions
        WHERE strftime('%Y-%m', payment_date) = ?
        GROUP BY payment_category
    """, (month_prefix,))
    month_rows = cursor.fetchall()

    breakdown_month = {
        "CASH_SALE": 0.0,
        "DOWN_PAYMENT": 0.0,
        "INSTALLMENT_MONTHLY": 0.0,
        "RENTAL_MONTHLY": 0.0,
        "SECURITY_DEPOSIT": 0.0,
        "PENALTY": 0.0
    }
    for r in month_rows:
        cat = r["payment_category"]
        if cat in breakdown_month:
            breakdown_month[cat] = float(r["total_uzs"])

    month_total_installment = breakdown_month["DOWN_PAYMENT"] + breakdown_month["INSTALLMENT_MONTHLY"]
    month_total_all = sum(breakdown_month.values())

    # 2. Barcha davrlar bo'yicha umumiy tushumlar (All-time)
    cursor.execute("""
        SELECT 
            payment_category,
            COALESCE(SUM(amount_uzs), 0) as total_uzs,
            COUNT(*) as txn_count
        FROM transactions
        GROUP BY payment_category
    """)
    all_time_rows = cursor.fetchall()

    breakdown_all_time = {
        "CASH_SALE": 0.0,
        "DOWN_PAYMENT": 0.0,
        "INSTALLMENT_MONTHLY": 0.0,
        "RENTAL_MONTHLY": 0.0,
        "SECURITY_DEPOSIT": 0.0,
        "PENALTY": 0.0
    }
    for r in all_time_rows:
        cat = r["payment_category"]
        if cat in breakdown_all_time:
            breakdown_all_time[cat] = float(r["total_uzs"])

    all_time_total = sum(breakdown_all_time.values())

    conn.close()

    return {
        "period": month_prefix,
        "month_revenue": {
            "cash_sales_uzs": breakdown_month["CASH_SALE"],
            "installment_down_payments_uzs": breakdown_month["DOWN_PAYMENT"],
            "installment_monthly_collections_uzs": breakdown_month["INSTALLMENT_MONTHLY"],
            "total_installment_revenue_uzs": month_total_installment,
            "rental_collections_uzs": breakdown_month["RENTAL_MONTHLY"],
            "other_collections_uzs": breakdown_month["SECURITY_DEPOSIT"] + breakdown_month["PENALTY"],
            "total_month_revenue_uzs": month_total_all
        },
        "all_time_revenue": {
            "cash_sales_uzs": breakdown_all_time["CASH_SALE"],
            "installment_revenue_uzs": breakdown_all_time["DOWN_PAYMENT"] + breakdown_all_time["INSTALLMENT_MONTHLY"],
            "rental_revenue_uzs": breakdown_all_time["RENTAL_MONTHLY"],
            "total_all_time_revenue_uzs": all_time_total
        }
    }

def get_fleet_and_sales_metrics() -> Dict[str, Any]:
    """Avtomobillar inventarizatsiyasi va sotuv/ijara soni ko'rsatkichlari"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Mashinalar holati bo'yicha sonlar
    cursor.execute("""
        SELECT status, COUNT(*) as count, COALESCE(SUM(sale_price_uzs), 0) as total_value_uzs
        FROM cars
        GROUP BY status
    """)
    status_rows = cursor.fetchall()
    counts = {"Available": 0, "Rented": 0, "Sold_Cash": 0, "Sold_Installment": 0}
    values = {"Available": 0.0, "Rented": 0.0, "Sold_Cash": 0.0, "Sold_Installment": 0.0}

    for r in status_rows:
        st = r["status"]
        if st in counts:
            counts[st] = r["count"]
            values[st] = float(r["total_value_uzs"])

    total_cars = sum(counts.values())
    total_sold = counts["Sold_Cash"] + counts["Sold_Installment"]

    # Shartnomalar bo'yicha jami faol qoldiq (Receivables)
    cursor.execute("""
        SELECT COALESCE(SUM(remaining_balance_uzs), 0) FROM contracts WHERE status = 'ACTIVE'
    """)
    total_receivables = cursor.fetchone()[0]

    conn.close()

    return {
        "total_cars_in_system": total_cars,
        "available_in_showroom": counts["Available"],
        "active_rentals_count": counts["Rented"],
        "sold_cash_count": counts["Sold_Cash"],
        "sold_installment_count": counts["Sold_Installment"],
        "total_sold_cars": total_sold,
        "fleet_utilization_rate_pct": round((counts["Rented"] + total_sold) / total_cars * 100, 1) if total_cars else 0,
        "total_active_receivables_uzs": float(total_receivables)
    }

def get_debtors_list() -> List[Dict[str, Any]]:
    """
    Qarzdorlar ro'yxati (To'lovni kechiktirganlar):
    Bo'lib to'lash bo'yicha OVERDUE bo'lganlar va Ijara qarzdorlari
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    now_str = datetime.now().strftime("%Y-%m-%d")

    # 1. Avval tizimdagi muddati o'tib ketgan, lekin hali PENDING turgan grafik yozuvlarini OVERDUE ga yangilab olamiz
    cursor.execute("""
        UPDATE installment_schedules
        SET status = 'OVERDUE'
        WHERE due_date < ? AND status = 'PENDING'
    """, (now_str,))
    conn.commit()

    # 2. Bo'lib to'lash qarzdorlari
    cursor.execute("""
        SELECT 
            cust.id as customer_id,
            cust.full_name as customer_name,
            cust.phone as customer_phone,
            car.id as car_id,
            car.model as car_model,
            car.plate_number,
            c.id as contract_id,
            c.contract_type,
            c.monthly_payment_uzs,
            COUNT(s.id) as overdue_months_count,
            COALESCE(SUM(s.amount_due_uzs - s.amount_paid_uzs), 0) as total_debt_uzs,
            COALESCE(SUM(s.penalty_uzs), 0) as total_penalty_uzs,
            MIN(s.due_date) as oldest_due_date
        FROM installment_schedules s
        JOIN contracts c ON s.contract_id = c.id
        JOIN customers cust ON c.customer_id = cust.id
        JOIN cars car ON c.car_id = car.id
        WHERE s.status = 'OVERDUE'
        GROUP BY cust.id, c.id
        ORDER BY total_debt_uzs DESC
    """)
    installment_debtors = cursor.fetchall()

    # 3. Ijara qarzdorlari (Amaldagi RENTAL bo'lib, to'lovi kutilayotganlar)
    cursor.execute("""
        SELECT 
            cust.id as customer_id,
            cust.full_name as customer_name,
            cust.phone as customer_phone,
            car.id as car_id,
            car.model as car_model,
            car.plate_number,
            c.id as contract_id,
            c.contract_type,
            c.monthly_payment_uzs,
            c.remaining_balance_uzs as total_debt_uzs,
            c.end_date as oldest_due_date
        FROM contracts c
        JOIN customers cust ON c.customer_id = cust.id
        JOIN cars car ON c.car_id = car.id
        WHERE c.contract_type = 'RENTAL' AND c.status = 'ACTIVE' AND c.remaining_balance_uzs > 0
    """)
    rental_debtors = cursor.fetchall()

    conn.close()

    now = datetime.now()
    debtors = []

    for r in installment_debtors:
        d = dict(r)
        d["debt_type"] = "MUDDATLI_TOLOV"
        try:
            oldest_dt = datetime.strptime(d["oldest_due_date"], "%Y-%m-%d")
            d["days_overdue"] = (now - oldest_dt).days
        except Exception:
            d["days_overdue"] = 0
        debtors.append(d)

    for r in rental_debtors:
        d = dict(r)
        d["debt_type"] = "IJARA_ARENDA"
        d["overdue_months_count"] = 1
        d["total_penalty_uzs"] = 0
        try:
            oldest_dt = datetime.strptime(d["oldest_due_date"], "%Y-%m-%d")
            d["days_overdue"] = max(0, (now - oldest_dt).days)
        except Exception:
            d["days_overdue"] = 0
        debtors.append(d)

    return debtors

def build_executive_summary_data() -> Dict[str, Any]:
    """Tizim egasi (Rahbariyat) uchun to'liq tahliliy ko'rsatkichlar to'plami"""
    revenue = get_revenue_breakdown()
    fleet = get_fleet_and_sales_metrics()
    debtors = get_debtors_list()

    total_debt_uzs = sum(d["total_debt_uzs"] for d in debtors)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kpi_overview": {
            "total_monthly_revenue_uzs": revenue["month_revenue"]["total_month_revenue_uzs"],
            "total_all_time_revenue_uzs": revenue["all_time_revenue"]["total_all_time_revenue_uzs"],
            "active_rentals_count": fleet["active_rentals_count"],
            "total_sold_cars": fleet["total_sold_cars"],
            "available_cars_count": fleet["available_in_showroom"],
            "fleet_utilization_pct": fleet["fleet_utilization_rate_pct"],
            "total_debtors_count": len(debtors),
            "total_overdue_debt_uzs": total_debt_uzs,
            "total_active_receivables_uzs": fleet["total_active_receivables_uzs"]
        },
        "revenue_breakdown": revenue["month_revenue"],
        "debtors_summary": {
            "count": len(debtors),
            "debtors": debtors[:5]  # Top 5 ta asosiy qarzdor
        }
    }
