import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from config import DB_PATH

def get_db_connection() -> sqlite3.Connection:
    """Ma'lumotlar bazasiga xavfsiz ulanish (row_factory va foreign keys yoqilgan)"""
    db_file = Path(DB_PATH)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db():
    """Barcha relyatsion jadvallarni yaratish va zarur bo'lsa dastlabki ma'lumotlarni yuklash"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Avtomobillar jadvali (Inventar)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            make TEXT NOT NULL DEFAULT 'Chevrolet',
            year INTEGER NOT NULL,
            vin TEXT UNIQUE NOT NULL,
            plate_number TEXT,
            color TEXT NOT NULL DEFAULT 'Oq (White)',
            mileage INTEGER NOT NULL DEFAULT 0,
            fuel_type TEXT NOT NULL DEFAULT 'Benzin',
            transmission TEXT NOT NULL DEFAULT 'Avtomat',
            purchase_price_usd REAL NOT NULL,
            sale_price_usd REAL NOT NULL,
            sale_price_uzs REAL NOT NULL,
            rental_price_daily_usd REAL NOT NULL DEFAULT 35.0,
            rental_price_monthly_usd REAL NOT NULL DEFAULT 650.0,
            rental_price_monthly_uzs REAL NOT NULL DEFAULT 8250000.0,
            status TEXT NOT NULL DEFAULT 'Available' 
                CHECK(status IN ('Available', 'Rented', 'Sold_Cash', 'Sold_Installment')),
            condition TEXT NOT NULL DEFAULT 'A''lo' 
                CHECK(condition IN ('Yangi', 'A''lo', 'Yaxshi', 'O''rtacha')),
            image_url TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Mijozlar jadvali (CRM Customers)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            passport_series TEXT,
            pinfl TEXT,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. Shartnomalar jadvali (Contracts: Ijara, Naqd sotuv, Bo'lib to'lash)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contracts (
            id TEXT PRIMARY KEY,
            contract_type TEXT NOT NULL 
                CHECK(contract_type IN ('SALE_CASH', 'SALE_INSTALLMENT', 'RENTAL')),
            car_id TEXT NOT NULL REFERENCES cars(id),
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            start_date TEXT NOT NULL,
            end_date TEXT,
            total_contract_uzs REAL NOT NULL,
            down_payment_uzs REAL NOT NULL DEFAULT 0,
            paid_amount_uzs REAL NOT NULL DEFAULT 0,
            remaining_balance_uzs REAL NOT NULL DEFAULT 0,
            monthly_payment_uzs REAL NOT NULL DEFAULT 0,
            term_months INTEGER DEFAULT 0,
            billing_day INTEGER NOT NULL DEFAULT 15,
            status TEXT NOT NULL DEFAULT 'ACTIVE' 
                CHECK(status IN ('ACTIVE', 'COMPLETED', 'DEFAULTED', 'TERMINATED')),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 4. Bo'lib to'lash jadvali (Installment Schedules: Paid / Pending / Overdue)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS installment_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
            installment_no INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            amount_due_uzs REAL NOT NULL,
            amount_paid_uzs REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'PENDING' 
                CHECK(status IN ('PAID', 'PENDING', 'OVERDUE')),
            paid_at TIMESTAMP,
            penalty_uzs REAL NOT NULL DEFAULT 0,
            notes TEXT
        )
    """)

    # 5. Moliya va To'lov tranzaksiyalari (Transactions Ledger)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_code TEXT UNIQUE NOT NULL,
            contract_id TEXT NOT NULL REFERENCES contracts(id),
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            car_id TEXT NOT NULL REFERENCES cars(id),
            schedule_id INTEGER REFERENCES installment_schedules(id),
            payment_category TEXT NOT NULL 
                CHECK(payment_category IN ('CASH_SALE', 'DOWN_PAYMENT', 'INSTALLMENT_MONTHLY', 'RENTAL_MONTHLY', 'PENALTY', 'SECURITY_DEPOSIT')),
            amount_uzs REAL NOT NULL,
            payment_method TEXT NOT NULL 
                CHECK(payment_method IN ('CASH', 'CLICK', 'PAYME', 'UZUM', 'BANK_TRANSFER')),
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reference_no TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 6. AI Bildirishnomalar va Eslatmalar (Notifications & Debtor Alerts)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id TEXT REFERENCES contracts(id),
            customer_id INTEGER REFERENCES customers(id),
            notification_type TEXT NOT NULL 
                CHECK(notification_type IN ('OVERDUE_ALERT', 'RENTAL_EXPIRY_ALERT', 'PAYMENT_RECEIVED', 'EXECUTIVE_REPORT')),
            recipient_phone TEXT NOT NULL,
            message TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'TELEGRAM' 
                CHECK(channel IN ('TELEGRAM', 'SMS', 'SYSTEM')),
            status TEXT NOT NULL DEFAULT 'PENDING' 
                CHECK(status IN ('PENDING', 'SENT', 'FAILED')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 7. Yangi mijoz qiziqishlari (Leads)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            car_id TEXT,
            interest_type TEXT NOT NULL DEFAULT 'INSTALLMENT',
            details TEXT,
            status TEXT NOT NULL DEFAULT 'yangi',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # Dastlabki ma'lumotlarni to'ldirish
    cursor.execute("SELECT COUNT(*) FROM cars")
    if cursor.fetchone()[0] == 0:
        seed_complete_database(cursor)
        conn.commit()

    conn.close()

def seed_complete_database(cursor: sqlite3.Cursor):
    """Realistik va to'liq dastlabki ma'lumotlar bilan to'ldirish"""
    now = datetime.now()
    cur_year = now.year

    # 1. Mashinalar
    cars = [
        # Available (Sotuvda / Bo'sh)
        ("CAR-101", "Chevrolet Cobalt 4-pozitsiya AT (Style)", "Chevrolet", 2024, "XWB4A11BFRA100101", "01 777 AAA", "Oq", 4200, "Benzin", "Avtomat", 11500, 13500, 171450000, 30, 550, 6985000, "Available", "Yangi", "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80", "Tejamkor, konditsioner, yangi shina, tayyor holatda."),
        ("CAR-102", "Chevrolet Onix Premier 2 Turbo", "Chevrolet", 2024, "XWB4A11BFRA100102", "01 888 BBB", "Qora metal", 8500, "Benzin (AI-95)", "Avtomat", 14200, 16500, 209550000, 40, 700, 8890000, "Available", "A'lo", "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?auto=format&fit=crop&w=800&q=80", "Lyuk, simsiz quvvatlash, zamonaviy salon, ideal holatda."),
        ("CAR-103", "BYD Song Plus Champion DM-i Flagship", "BYD", 2024, "LC0CE40E5RA200103", "01 999 CCC", "Kulrang (Grey)", 12000, "Gibrid (Elektr/Benzin)", "Avtomat", 25000, 28500, 361950000, 65, 1200, 15240000, "Available", "A'lo", "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80", "110 km elektr yurish zaxirasi, 360 kamera, moslashuvchan kruiz."),
        ("CAR-104", "Kia K5 Luxe 2.0 AT", "Kia", 2024, "KNAGE414BPA300104", "01 444 DDD", "Oq marvarid", 15000, "Benzin", "Avtomat", 23500, 27000, 342900000, 60, 1100, 13970000, "Available", "A'lo", "https://images.unsplash.com/photo-1617814076367-b759c7d7e738?auto=format&fit=crop&w=800&q=80", "Biznes klass sedan, sport dizayn, akustik qulaylik."),

        # Rented (Arendaga berilgan)
        ("CAR-201", "Chevrolet Gentra (Lacetti) 3-pozitsiya AT", "Chevrolet", 2023, "XWB4A11BFRA200201", "01 M 890 BA", "Oq", 38000, "Benzin / Gaz", "Avtomat", 11800, 13800, 175260000, 28, 500, 6350000, "Rented", "Yaxshi", "https://images.unsplash.com/photo-1541899481282-d53bffe3c35d?auto=format&fit=crop&w=800&q=80", "Arendaga topshirilgan, metan gaz o'rnatilgan."),
        ("CAR-202", "Chevrolet Tracker 2 Premier Redline", "Chevrolet", 2023, "XWB4A11BFRA200202", "10 B 123 BB", "Qizil / Qora tom", 22000, "Benzin", "Avtomat", 18500, 21200, 269240000, 45, 800, 10160000, "Rented", "A'lo", "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=800&q=80", "Arendaga berilgan, xavfsizlik datchiklari, panorama tom."),

        # Sold_Cash (Naqdga sotilgan)
        ("CAR-301", "Chevrolet Malibu 2 Premier 2.0 Turbo", "Chevrolet", 2023, "XWB4A11BFRA300301", "01 A 001 VIP", "Qora", 18000, "Benzin", "Avtomat", 27000, 31000, 393700000, 70, 1300, 16510000, "Sold_Cash", "A'lo", "https://images.unsplash.com/photo-1550355291-bbee04a92027?auto=format&fit=crop&w=800&q=80", "To'liq naqd to'lov bilan sotilgan."),

        # Sold_Installment (Bo'lib to'lashga berilgan)
        ("CAR-401", "Chevrolet Cobalt 4-pozitsiya AT (2023)", "Chevrolet", 2023, "XWB4A11BFRA400401", "01 A 777 AA", "Oq", 29000, "Benzin", "Avtomat", 11000, 13000, 165100000, 28, 520, 6604000, "Sold_Installment", "Yaxshi", "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80", "24 oylik muddatli to'lov shartnomasi bo'yicha berilgan."),
        ("CAR-402", "Chevrolet Tracker 2 Redline (2024)", "Chevrolet", 2024, "XWB4A11BFRA400402", "01 X 555 XX", "Oq / Qora", 11000, "Benzin", "Avtomat", 18800, 21500, 273050000, 45, 800, 10160000, "Sold_Installment", "A'lo", "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=800&q=80", "18 oylik bo'lib to'lashga rasmiylashtirilgan.")
    ]
    cursor.executemany("""
        INSERT INTO cars (
            id, model, make, year, vin, plate_number, color, mileage,
            fuel_type, transmission, purchase_price_usd, sale_price_usd,
            sale_price_uzs, rental_price_daily_usd, rental_price_monthly_usd,
            rental_price_monthly_uzs, status, condition, image_url, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, cars)

    # 2. Mijozlar
    customers = [
        (1, "Anvar Karimov", "+998901234567", "AA1234567", "30101900010011", "Toshkent sh., Chilonzor tumani 9-mavze, 12-uy"),
        (2, "Jasurbek Rahimov", "+998998887766", "AB7654321", "31205930020022", "Toshkent viloyati, Yangiyo'l tumani, Guliston ko'chasi 45-uy"),
        (3, "Dilshod Umarov", "+998971112233", "AC9988776", "31508880030033", "Toshkent sh., Yunusobod 14-mavze, 5-uy"),
        (4, "Otabek Mansurov", "+998935554433", "AD5544332", "32204950040044", "Samarqand sh., Mirzo Ulug'bek ko'chasi 88-uy"),
        (5, "Sherzod Aliyev", "+998946661122", "AE1122334", "30907920050055", "Toshkent sh., Mirabad tumani, Afrosiyob ko'chasi 14-uy")
    ]
    cursor.executemany("""
        INSERT INTO customers (id, full_name, phone, passport_series, pinfl, address)
        VALUES (?, ?, ?, ?, ?, ?)
    """, customers)

    # 3. Shartnomalar
    # CTR-CASH-01: Dilshod Umarov (CAR-301 Malibu)
    # CTR-INST-01: Anvar Karimov (CAR-401 Cobalt) - 24 oy, to'lovlar o'z vaqtida
    # CTR-INST-02: Jasurbek Rahimov (CAR-402 Tracker) - 18 oy, qarzga botgan (OVERDUE bor)
    # CTR-RENT-01: Sherzod Aliyev (CAR-201 Gentra) - Oylik ijara, to'langan
    # CTR-RENT-02: Otabek Mansurov (CAR-202 Tracker) - Oylik ijara, muddati o'tib ketgan (OVERDUE)

    contracts = [
        (
            "CTR-CASH-001", "SALE_CASH", "CAR-301", 3,
            (now - timedelta(days=45)).strftime("%Y-%m-%d"), (now - timedelta(days=45)).strftime("%Y-%m-%d"),
            393700000, 393700000, 393700000, 0, 0, 0, 1, "COMPLETED", "Naqd to'liq to'langan"
        ),
        (
            "CTR-INST-001", "SALE_INSTALLMENT", "CAR-401", 1,
            (now - timedelta(days=180)).strftime("%Y-%m-%d"), (now + timedelta(days=540)).strftime("%Y-%m-%d"),
            214630000, 50000000, 84360000, 130270000, 6860000, 24, 15, "ACTIVE", "Oylik 6.86 mln so'm, o'z vaqtida to'lanmoqda"
        ),
        (
            "CTR-INST-002", "SALE_INSTALLMENT", "CAR-402", 2,
            (now - timedelta(days=90)).strftime("%Y-%m-%d"), (now + timedelta(days=450)).strftime("%Y-%m-%d"),
            341310000, 70000000, 70000000, 271310000, 15073000, 18, 10, "ACTIVE", "Boshlang'ich to'lov qilingan, oxirgi 2 oy to'lov kechikkan (Qarzdor!)"
        ),
        (
            "CTR-RENT-001", "RENTAL", "CAR-201", 5,
            (now - timedelta(days=60)).strftime("%Y-%m-%d"), (now + timedelta(days=30)).strftime("%Y-%m-%d"),
            19050000, 6350000, 12700000, 6350000, 6350000, 3, 20, "ACTIVE", "3 oylik arenda, 2 oyi to'langan"
        ),
        (
            "CTR-RENT-002", "RENTAL", "CAR-202", 4,
            (now - timedelta(days=45)).strftime("%Y-%m-%d"), (now + timedelta(days=15)).strftime("%Y-%m-%d"),
            20320000, 10160000, 10160000, 10160000, 10160000, 2, 5, "ACTIVE", "2 oylik ijara, navbatdagi oy to'lovi kechikkan (Arenda qarzdori!)"
        )
    ]
    cursor.executemany("""
        INSERT INTO contracts (
            id, contract_type, car_id, customer_id, start_date, end_date,
            total_contract_uzs, down_payment_uzs, paid_amount_uzs, remaining_balance_uzs,
            monthly_payment_uzs, term_months, billing_day, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, contracts)

    # 4. Bo'lib to'lash jadvali (Installment Schedules)
    # CTR-INST-001: 24 oylik. 1-5 oylari to'langan (PAID), 6-oy PENDING
    schedules = []
    # 5 ta to'langan oy
    for i in range(1, 6):
        d = (now - timedelta(days=(6 - i) * 30)).strftime("%Y-%m-%d")
        schedules.append(("CTR-INST-001", i, d, 6860000, 6860000, "PAID", d + " 14:30:00", 0, "O'z vaqtida to'landi"))
    # 6-oy (hozirgi oy, PENDING)
    due_p = (now + timedelta(days=10)).strftime("%Y-%m-%d")
    schedules.append(("CTR-INST-001", 6, due_p, 6860000, 0, "PENDING", None, 0, "Kutilayotgan navbatdagi to'lov"))
    # qolgan oylar PENDING
    for i in range(7, 25):
        d = (now + timedelta(days=(i - 5) * 30)).strftime("%Y-%m-%d")
        schedules.append(("CTR-INST-001", i, d, 6860000, 0, "PENDING", None, 0, "Rejadagi to'lov"))

    # CTR-INST-002: 18 oylik. Jasurbek Rahimov. 1-oy to'lanmagan (OVERDUE), 2-oy OVERDUE
    d_overdue1 = (now - timedelta(days=50)).strftime("%Y-%m-%d")
    d_overdue2 = (now - timedelta(days=20)).strftime("%Y-%m-%d")
    schedules.append(("CTR-INST-002", 1, d_overdue1, 15073000, 0, "OVERDUE", None, 450000, "Kechikkan to'lov (1-oy)"))
    schedules.append(("CTR-INST-002", 2, d_overdue2, 15073000, 0, "OVERDUE", None, 150000, "Kechikkan to'lov (2-oy)"))
    for i in range(3, 19):
        d = (now + timedelta(days=(i - 2) * 30)).strftime("%Y-%m-%d")
        schedules.append(("CTR-INST-002", i, d, 15073000, 0, "PENDING", None, 0, "Rejadagi to'lov"))

    cursor.executemany("""
        INSERT INTO installment_schedules (
            contract_id, installment_no, due_date, amount_due_uzs,
            amount_paid_uzs, status, paid_at, penalty_uzs, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, schedules)

    # 5. Tranzaksiyalar (Transactions Ledger)
    txns = [
        # Naqd sotuv (CTR-CASH-001)
        ("TXN-2026-0001", "CTR-CASH-001", 3, "CAR-301", None, "CASH_SALE", 393700000, "BANK_TRANSFER", (now - timedelta(days=45)).strftime("%Y-%m-%d 11:20:00"), "BNK-990182", "Avtomobil to'liq naqd sotuvi"),
        # Bo'lib to'lash boshlang'ich to'lovi (CTR-INST-001)
        ("TXN-2026-0002", "CTR-INST-001", 1, "CAR-401", None, "DOWN_PAYMENT", 50000000, "CASH", (now - timedelta(days=180)).strftime("%Y-%m-%d 15:00:00"), "CSH-0012", "Boshlang'ich to'lov"),
        # Oylik to'lovlar CTR-INST-001
        ("TXN-2026-0003", "CTR-INST-001", 1, "CAR-401", 1, "INSTALLMENT_MONTHLY", 6860000, "CLICK", (now - timedelta(days=150)).strftime("%Y-%m-%d 10:15:00"), "CLK-5521", "1-oy to'lovi"),
        ("TXN-2026-0004", "CTR-INST-001", 1, "CAR-401", 2, "INSTALLMENT_MONTHLY", 6860000, "PAYME", (now - timedelta(days=120)).strftime("%Y-%m-%d 14:40:00"), "PAY-9932", "2-oy to'lovi"),
        ("TXN-2026-0005", "CTR-INST-001", 1, "CAR-401", 3, "INSTALLMENT_MONTHLY", 6860000, "CLICK", (now - timedelta(days=90)).strftime("%Y-%m-%d 09:30:00"), "CLK-7741", "3-oy to'lovi"),
        ("TXN-2026-0006", "CTR-INST-001", 1, "CAR-401", 4, "INSTALLMENT_MONTHLY", 6860000, "UZUM", (now - timedelta(days=60)).strftime("%Y-%m-%d 16:10:00"), "UZM-1120", "4-oy to'lovi"),
        ("TXN-2026-0007", "CTR-INST-001", 1, "CAR-401", 5, "INSTALLMENT_MONTHLY", 6860000, "CLICK", (now - timedelta(days=30)).strftime("%Y-%m-%d 11:05:00"), "CLK-8839", "5-oy to'lovi"),

        # CTR-INST-002 boshlang'ich to'lov
        ("TXN-2026-0008", "CTR-INST-002", 2, "CAR-402", None, "DOWN_PAYMENT", 70000000, "BANK_TRANSFER", (now - timedelta(days=90)).strftime("%Y-%m-%d 16:30:00"), "BNK-44321", "Boshlang'ich to'lov"),

        # Arenda to'lovlari CTR-RENT-001
        ("TXN-2026-0009", "CTR-RENT-001", 5, "CAR-201", None, "RENTAL_MONTHLY", 6350000, "PAYME", (now - timedelta(days=60)).strftime("%Y-%m-%d 12:00:00"), "PAY-1123", "1-oy ijara to'lovi"),
        ("TXN-2026-0010", "CTR-RENT-001", 5, "CAR-201", None, "RENTAL_MONTHLY", 6350000, "CLICK", (now - timedelta(days=30)).strftime("%Y-%m-%d 13:25:00"), "CLK-3321", "2-oy ijara to'lovi"),

        # Arenda to'lovi CTR-RENT-002
        ("TXN-2026-0011", "CTR-RENT-002", 4, "CAR-202", None, "RENTAL_MONTHLY", 10160000, "CASH", (now - timedelta(days=45)).strftime("%Y-%m-%d 10:00:00"), "CSH-0089", "1-oy ijara to'lovi"),

        # Joriy oy to'lovlari (Current month collections)
        ("TXN-2026-0012", "CTR-RENT-001", 5, "CAR-201", None, "RENTAL_MONTHLY", 6350000, "CLICK", (now - timedelta(days=1, hours=3)).strftime("%Y-%m-%d %H:%M:%S"), "CLK-CURR-01", "Joriy oy arenda to'lovi"),
        ("TXN-2026-0013", "CTR-INST-001", 1, "CAR-401", 5, "INSTALLMENT_MONTHLY", 6860000, "PAYME", (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"), "PAY-CURR-02", "Joriy oy bo'lib to'lash to'lovi")
    ]
    cursor.executemany("""
        INSERT INTO transactions (
            transaction_code, contract_id, customer_id, car_id, schedule_id,
            payment_category, amount_uzs, payment_method, payment_date, reference_no, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, txns)

    # 6. Eslatmalar
    notifications = [
        ("CTR-INST-002", 2, "OVERDUE_ALERT", "+998998887766", "Hurmatli Jasurbek Rahimov! Tracker 2 (01 X 555 XX) bo'lib to'lash shartnomangiz bo'yicha 2 oylik to'lov (jami 30,746,000 so'm) kechikmoqda. Iltimos, zudlik bilan to'lovni amalga oshiring.", "TELEGRAM", "SENT"),
        ("CTR-RENT-002", 4, "RENTAL_EXPIRY_ALERT", "+998935554433", "Hurmatli Otabek Mansurov! Tracker 2 (10 B 123 BB) arenda shartnomangiz muddati 15 kundan so'ng tugaydi va joriy oy to'lovi kutilmoqda.", "SMS", "SENT")
    ]
    cursor.executemany("""
        INSERT INTO notifications (
            contract_id, customer_id, notification_type, recipient_phone, message, channel, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, notifications)
