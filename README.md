# 🚗 Baraka Avto AI — Dealership & Rental CRM & ERP System

Avtosalonlar va mashina ijarasi (arenda / muddatli to'lov) bilan shug'ullanuvchi bizneslar uchun mo'ljallangan **AI Agent integratsiyalashgan to'liq CRM & ERP tizimi**.

Ushbu tizim avtomobillar hisobi, sotuv (naqd va bo'lib to'lash), ijara jarayonlari, to'lovlar monitoringi, qarzdorlarni aniqlash va tabiiy tildagi savollarga (NLQ) javob beruvchi **AI Agent Copilot**ni o'z ichiga oladi.

---

## 🌟 Asosiy Imkoniyatlar (Core Features)

1. **Avtomobillar Inventarizatsiyasi (Inventory Management):**
   - Holatlar (Status): `Available` (Bo'sh/Sotuvda), `Rented` (Arendada), `Sold_Cash` (Naqd sotilgan), `Sold_Installment` (Bo'lib to'lashda).
   - VIN kod, davlat raqami, texnik parametrlar, tannarx, sotuv narxi va oylik ijara stavkasi hisobi.

2. **Sotuv Bo'limi (Sales Management):**
   - **Naqd sotuv (Cash Sales):** To'liq to'lov qayd etiladi va mashina statusi darhol `Sold_Cash` ga o'tkaziladi.
   - **Bo'lib to'lash (Installment Sales):** Boshlang'ich to'lov, ustama foiz hisob-kitobi va to'liq oylik amortizatsiya grafigi shakllanadi. Har bir oy `PAID`, `PENDING` yoki `OVERDUE` holatida yuritiladi.

3. **Ijara Bo'limi (Rental Management):**
   - Faol arendalar hisobi, kunlik va oylik ijara muddatlari.
   - Muddati tugayotgan yoki to'lovi kechikkan avtomobillarni avtomatik aniqlash.

4. **Tranzaksiyalar va Ma'lumot Integratsiyasi (Transactions & Details):**
   - Har qanday to'lov qabul qilinganda, ekranda o'sha avtomobilning to'liq kartochkasi (egasi, modeli, VIN, qoldiq qarzi, navbatdagi to'lov sanasi) avtomatik shakllanadi.

5. **AI Boshqaruv Maslahatchisi (Executive AI Copilot):**
   - Foydalanuvchining o'zbek tilidagi savollariga ("Bu oy qancha foyda qildik?", "Kimlarni arendadan qarzi bor?", "Executive summary ber") bazadan jonli ma'lumotlarni yig'ib, tahliliy javob beradi.
   - OpenAI (`gpt-4o-mini`) va Google Gemini API bilan Tool Calling orqali ishlaydi (API kalit kiritilmaganda aqlli ichki semantik tahlilchi rejimida ishlaydi).
   - Qarzdorlarga avtomatik SMS / Telegram eslatmalarini yuborish.

---

## 🏗️ Arxitektura va Fayllar Tuzilishi

```
Moshina arenda ai agent/
├── config.py                  # Konfiguratsiya va muhit o'zgaruvchilari
├── requirements.txt           # Kerakli Python kutubxonalari
├── main.py                    # FastAPI server va Web Dashboard ishga tushirish fayli
├── bot.py                     # Telegram Bot interfeysi (aiogram 3)
├── database/
│   ├── __init__.py
│   ├── db.py                  # SQLite/PostgreSQL DDL schema, migratsiya va seed data
│   └── models.py              # Pydantic ma'lumotlar modellari
├── services/
│   ├── __init__.py
│   ├── inventory_service.py   # Avtomobillar inventari va holatlar boshqaruvi
│   ├── sales_service.py       # Naqd va bo'lib to'lash, amortizatsiya hisoblari
│   ├── rental_service.py      # Ijara shartnomalari va muddatlar hisobi
│   ├── transaction_service.py # To'lovlarni qabul qilish va avto kartochkasini shakllantirish
│   └── analytics_service.py   # Oylik tushum, qarzdorlar va executive summary hisobotlari
├── agent/
│   ├── __init__.py
│   ├── prompts.py             # AI Agent tizim ko'rsatmasi va guardrails
│   ├── tools.py               # AI Tool Calling asboblari va JSON sxemalari
│   ├── agent_runner.py        # OpenAI/Gemini Tool Calling + O'zbekcha Semantik NLQ dvigateli
│   └── scheduler.py          # Qarzdorlik va ijara muddatini tekshiruvchi fon skaneri
└── static/
    ├── index.html             # Responsive TailwindCSS Web Dashboard
    └── app.js                 # Chart.js, to'lovlar, modallar va AI Chat mantiqi
```

---

## 🚀 O'rnatish va Ishga Tushirish

### 1. Kutubxonalarni o'rnatish:
```bash
pip install -r requirements.txt
```

### 2. Sozlamalarni kiritish (.env):
`.env.example` faylidan nusxa olib, `.env` faylini yarating:
```env
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_or_gemini_api_key
OPENAI_MODEL=gpt-4o-mini
```

### 3. ERP Tizimi va Web Dashboardni ishga tushirish:
```bash
python main.py
```
Brauzer orqali oching:
* 🌐 **Web Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* 📑 **Interactive API Docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 4. Telegram Botni ishga tushirish:
```bash
python bot.py
```

### 🤖 Telegram Bot Buyruqlari:
* `/commands` yoki `/help` — Barcha buyruqlar va imkoniyatlar ro'yxati
* `/revenue` — Joriy oy tushumlari (Naqd, Bo'lib to'lash, Ijara)
* `/debtors` — To'lov muddati o'tgan qarzdorlar ro'yxati
* `/summary` — Rahbariyat uchun Executive Summary hisoboti
* `/fleet` — Salondagi, arendadagi va sotilgan avtomobillar soni
* `/rentals` — Faol ijaradagi mashinalar va qolgan kunlar
* `/remind` — Qarzdorlarga avtomatik eslatmalar jo'natish
* `/clear` — AI suhbat tarixini tozalash

---

## 📊 API Endpointlar Ro'yxati

| Metod | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/cars` | Barcha avtomobillar ro'yxati (Status bo'yicha filter) |
| `POST` | `/api/cars` | Yangi avtomobil qo'shish |
| `POST` | `/api/sales/cash` | Naqd pulga sotuvni rasmiylashtirish |
| `POST` | `/api/sales/installment` | Bo'lib to'lash shartnomasi va jadvalini yaratish |
| `GET` | `/api/sales/contracts/{id}/schedule` | Oylik to'lovlar jadvali (Paid/Pending/Overdue) |
| `POST` | `/api/rentals` | Mashinani ijaraga (arenda) berish |
| `GET` | `/api/rentals/active` | Faol ijaradagi mashinalar va qoldiq kunlar |
| `POST` | `/api/payments` | To'lovni qayd etish va mashina kartochkasini olish |
| `GET` | `/api/payments/ledger` | Barcha to'lovlar tranzaksiya jurnali |
| `GET` | `/api/analytics/monthly-revenue` | Oylik tushumlar tarkibi (Naqd, Bo'lib to'lash, Ijara) |
| `GET` | `/api/analytics/debtors` | Qarzdorlar ro'yxati va kechikkan kunlar |
| `GET` | `/api/analytics/executive-summary` | Rahbariyat uchun tahliliy hisobot |
| `POST` | `/api/ai/chat` | AI Copilot bilan tabiiy tildagi muloqot |
| `POST` | `/api/ai/check-reminders` | Qarzdorlarga avtomatik eslatmalar yuborish |
