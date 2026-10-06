import json
import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from agent.prompts import SYSTEM_PROMPT, EXECUTIVE_SUMMARY_TEMPLATE
from agent.tools import (
    TOOLS_DEFINITIONS,
    execute_tool_call,
    tool_get_monthly_revenue_report,
    tool_get_debtors_report,
    tool_get_fleet_inventory_status,
    tool_get_car_and_contract_details,
    tool_generate_executive_summary_report,
    tool_trigger_overdue_reminders,
    tool_search_available_cars
)

logger = logging.getLogger(__name__)

class AIAgent:
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.base_url = OPENAI_BASE_URL
        self.model = OPENAI_MODEL

        # Gemini API kaliti bo'lsa
        if self.api_key and self.api_key.startswith("AIzaSy") and not self.base_url:
            self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

        if self.api_key and self.api_key != "your_openai_or_gemini_api_key_here":
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            self.is_llm_active = True
        else:
            self.client = None
            self.is_llm_active = False

        self.sessions: Dict[str, List[Dict[str, Any]]] = {}

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        if session_id not in self.sessions:
            self.sessions[session_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
        return self.sessions[session_id]

    def reset_history(self, session_id: str):
        self.sessions[session_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    async def process_message(self, message: str, session_id: str = "default_session") -> Dict[str, Any]:
        """
        Foydalanuvchi so'rovini qabul qilish.
        Agar LLM API mavjud bo'lsa, Tool Calling orqali ishlaydi.
        Agar API kalit yo'q bo'lsa, aqlli semantik tahlilchi (rule-based NLP) orqali ishlaydi.
        """
        user_msg = message.strip()
        history = self.get_history(session_id)
        history.append({"role": "user", "content": user_msg})

        # LLM bilan ishlash
        if self.is_llm_active and self.client:
            try:
                for _ in range(5):
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=history,
                        tools=TOOLS_DEFINITIONS,
                        tool_choice="auto",
                        temperature=0.2
                    )
                    resp_msg = response.choices[0].message
                    tool_calls = resp_msg.tool_calls

                    if tool_calls:
                        history.append(resp_msg)
                        executed_tools_info = []

                        for tc in tool_calls:
                            fn_name = tc.function.name
                            try:
                                fn_args = json.loads(tc.function.arguments)
                            except Exception:
                                fn_args = {}

                            logger.info(f"AI Tool chaqirmoqda: {fn_name}({fn_args})")
                            tool_out = execute_tool_call(fn_name, fn_args)
                            executed_tools_info.append({"tool": fn_name, "args": fn_args, "result": json.loads(tool_out) if isinstance(tool_out, str) and tool_out.startswith("{") else tool_out})

                            history.append({
                                "tool_call_id": tc.id,
                                "role": "tool",
                                "name": fn_name,
                                "content": tool_out
                            })
                    else:
                        reply_text = resp_msg.content or "Ma'lumot topildi."
                        history.append({"role": "assistant", "content": reply_text})
                        return {
                            "response": reply_text,
                            "mode": "llm_function_calling",
                            "model": self.model
                        }
            except Exception as e:
                logger.warning(f"LLM orqali bajarishda xatolik yuz berdi: {e}. Semantik rejimga o'tilmoqda.")

        # Fallback / Offline Semantic Intent Matcher (Kafolatlangan aniq javoblar)
        return self._semantic_offline_processor(user_msg)

    def _semantic_offline_processor(self, query: str) -> Dict[str, Any]:
        """API kalitsiz ham natural language savollarga professional javob berish"""
        q = query.lower()

        # 1. Tushum va Foyda haqidagi so'rovlar ("Bu oy qancha foyda qildik?", "Oylik tushum")
        if any(w in q for w in ["foyda", "tushum", "daromad", "qancha pul", "tushdi", "kassa", "oborot", "revenue"]):
            raw = tool_get_monthly_revenue_report()
            data = json.loads(raw)
            text = (
                f"### 💰 **Oylik Tushumlar va Moliya Hisoboti ({data['davr']})**\n\n"
                f"Joriy oyda tizim bo'yicha tushgan umumiy mablag'lar tahlili:\n\n"
                f"* 💵 **Naqd sotuvdan tushum:** {data['naqd_sotuvdan_tushum']}\n"
                f"* 📄 **Bo'lib to'lash (Boshlang'ich badallar):** {data['bolib_tolash_boshlangich']}\n"
                f"* 📆 **Bo'lib to'lash (Oylik yig'imlar):** {data['bolib_tolash_oylik_yigimlar']}\n"
                f"* 🤝 **Bo'lib to'lash jami tushumi:** {data['bolib_tolash_jami']}\n"
                f"* 🔑 **Ijara (Arenda) to'lovlari:** {data['arenda_ijara_tushumi']}\n"
                f"---\n"
                f"### 🏆 **JAMI JORIY OY TUSHUMI: {data['joriy_oy_jami_tushumi']}**\n"
                f"*Barcha davrlar bo'yicha yig'ilgan jami tushum:* **{data['barcha_davrlar_jami_tushumi']}**\n\n"
                f"💡 *Tavsiya:* Bo'lib to'lash oylik to'lovlarining yig'ilish ko'rsatkichini oshirish uchun qarzdorlarga eslatma yuborish tavsiya etiladi."
            )
            return {"response": text, "mode": "semantic_nlq", "data": data}

        # 2. Qarzdorlar haqidagi so'rovlar ("Kimlarni arendadan qarzi bor?", "Qarzdorlar")
        if any(w in q for w in ["qarz", "qarzdor", "kechikkan", "tolamagan", "to'lamagan", "overdue", "debt"]):
            filter_type = "ALL"
            if "arenda" in q or "ijara" in q:
                filter_type = "RENTAL"
            elif "bo'lib" in q or "bolib" in q or "nasiya" in q:
                filter_type = "INSTALLMENT"

            raw = tool_get_debtors_report(filter_type)
            data = json.loads(raw)

            if data.get("status") == "clean":
                return {"response": "✅ **Hozirda qarzdorlar mavjud emas!** Barcha mijozlar to'lovlarni o'z vaqtida amalga oshirgan.", "mode": "semantic_nlq", "data": data}

            debtor_rows = ""
            for i, d in enumerate(data.get("qarzdorlar", []), 1):
                debtor_rows += (
                    f"| {i} | **{d['mijoz']}** | {d['telefon']} | {d['avtomobil']} | {d['turi']} | "
                    f"**{d['qarz_summasi']}** | {d['kechikkan_kunlar']} kun |\n"
                )

            text = (
                f"### ⚠️ **To'lovni Kechiktirgan Qarzdorlar Ro'yxati**\n\n"
                f"Tizimda jami **{data['jami_qarzdorlar_soni']} nafar** qarzdor aniqlandi.\n"
                f"Jami kechikkan xavfli qarz summasi: **{data['jami_kechikkan_summa']}**\n\n"
                f"| № | Mijoz | Telefon | Avtomobil | Shartnoma | Qarz Summasi | Kechikish |\n"
                f"|---|---|---|---|---|---|---|\n"
                f"{debtor_rows}\n"
                f"🔔 *AI Agent maslahati:* Ushbu mijozlarga avtomatik SMS / Telegram eslatma jo'natish uchun *\"Qarzdorlarga eslatma jo'nat\"* deb yozing."
            )
            return {"response": text, "mode": "semantic_nlq", "data": data}

        # 3. Executive summary / Biznes holati
        if any(w in q for w in ["summary", "executive", "hisobot", "rahbar", "biznes", "kpi", "overview", "holat"]):
            raw = tool_generate_executive_summary_report()
            data = json.loads(raw)
            recs = "\n".join([f"- {r}" for r in data["strategik_tavsiyalar"]])
            text = (
                f"### 📊 **Boshqaruv Tahlili (Executive Summary)**\n"
                f"*Sana: {data['sana']}*\n\n"
                f"#### 📈 Moliyaviy Ko'rsatkichlar:\n"
                f"* 💰 **Joriy oy tushumi:** {data['joriy_oy_tushumi']}\n"
                f"* 🌐 **Barcha davrlar tushumi:** {data['barcha_davrlar_tushumi']}\n"
                f"* 🏦 **Faol kutilayotgan qarzlar portfeli:** {data['faol_kutilayotgan_portfel']}\n"
                f"* ⚠️ **Muddati o'tgan xavfli qarz:** {data['xavfli_kechikkan_qarz_summasi']} ({data['qarzdorlar_soni']} nafar qarzdor)\n\n"
                f"#### 🚗 Avtopark va Sotuv Holati:\n"
                f"* 🟢 Salonda sotuvga tayyor: **{data['salondagi_bosh_mashinalar']} ta**\n"
                f"* 🔑 Arendaga berilgan: **{data['faol_arendadagi_mashinalar']} ta**\n"
                f"* 🤝 Jami sotilgan: **{data['jami_sotilgan_mashinalar']} ta**\n"
                f"* ⚡ Avtoparkdan foydalanish samaradorligi: **{data['avtopark_samaradorligi']}**\n\n"
                f"#### 🧠 AI Strategik Tavsiyalari:\n{recs}"
            )
            return {"response": text, "mode": "semantic_nlq", "data": data}

        # 4. Mashinalar inventari ("Mavjud mashinalar", "Arendadagi mashinalar", "Inventar")
        if any(w in q for w in ["mashina", "avto", "inventar", "salonda", "mavjud", "bosh", "bo'sh", "avtomobil"]):
            # Agar muayyan mashina nomi yoki raqami bo'lsa
            for model_keyword in ["tracker", "cobalt", "onix", "gentra", "malibu", "byd", "k5", "damas", "01", "10"]:
                if model_keyword in q:
                    raw_car = tool_get_car_and_contract_details(model_keyword)
                    car_data = json.loads(raw_car)
                    if car_data.get("status") == "found":
                        shartnoma_txt = ""
                        if isinstance(car_data.get("amaldagi_shartnoma"), dict):
                            s = car_data["amaldagi_shartnoma"]
                            shartnoma_txt = (
                                f"\n\n**Amaldagi Shartnoma Ma'lumotlari:**\n"
                                f"* 👤 Mijoz: **{s['mijoz_ismi']}** ({s['mijoz_telefoni']})\n"
                                f"* 📑 Turi: **{s['turi']}** ({s['shartnoma_holati']})\n"
                                f"* 💵 Qoldiq qarz: **{s['qoldiq_qarz']}**\n"
                                f"* 📅 Oylik to'lov: **{s['oylik_tolov']}**"
                            )
                        else:
                            shartnoma_txt = f"\n\n*Holat:* {car_data['amaldagi_shartnoma']}"

                        text = (
                            f"### 🚗 **Avtomobil Kartochkasi: {car_data['model']}**\n"
                            f"* **Davlat raqami:** `{car_data['davlat_raqami']}`\n"
                            f"* **VIN kod:** `{car_data['vin']}`\n"
                            f"* **Yili:** {car_data['ishlab_chiqarilgan_yili']}-yil\n"
                            f"* **Status:** `{car_data['holati']}`\n"
                            f"* **Narxi (Sotuv):** {car_data['umumiy_narxi']}\n"
                            f"* **Oylik ijara narxi:** {car_data['oylik_ijara_narxi']}"
                            f"{shartnoma_txt}"
                        )
                        return {"response": text, "mode": "semantic_nlq", "data": car_data}

            # Umumiy inventar
            raw = tool_get_fleet_inventory_status()
            data = json.loads(raw)
            text = (
                f"### 🚘 **Avtopark Inventarizatsiyasi**\n\n"
                f"* 🚙 Jami mashinalar: **{data['jami_mashinalar_soni']} ta**\n"
                f"* 🟢 Sotuvda tayyor (Available): **{data['salonda_tayyor_bosh']} ta**\n"
                f"* 🔑 Ijarada (Rented): **{data['arendadagi_mashinalar']} ta**\n"
                f"* 💵 Naqd sotilgan (Sold Cash): **{data['naqd_sotilganlar']} ta**\n"
                f"* 📑 Bo'lib to'lashda (Sold Installment): **{data['bolib_tolashga_berilganlar']} ta**\n"
                f"* 📊 Avtopark bandligi: **{data['parkdan_foydalanish_foizi']}**\n"
                f"* 💼 Faol kutilayotgan haqlar portfeli: **{data['faol_kutilayotgan_haqlar_portfeli']}**\n\n"
                f"Muayyan model (masalan *Tracker*, *Cobalt* yoki davlat raqami) bo'yicha to'liq ma'lumot olishingiz mumkin."
            )
            return {"response": text, "mode": "semantic_nlq", "data": data}

        # 5. Eslatmalar yuborish ("eslatma", "sms", "xabar jo'nat")
        if any(w in q for w in ["eslatma", "xabarnoma", "jonat", "jo'nat", "sms", "alert"]):
            raw = tool_trigger_overdue_reminders()
            data = json.loads(raw)
            text = (
                f"### 🔔 **Qarzdorlarga Eslatmalar Muvaffaqiyatli Yuborildi!**\n\n"
                f"Jami **{data['yuborilgan_bildirishnomalar_soni']} ta** eslatma xabarnomasi shakllantirildi va mijozlarga yo'llandi:\n"
            )
            for t in data.get("tafsilotlar", []):
                text += f"- 👤 **{t['mijoz']}** ({t['telefon']}) — Qarz: `{t['summa']}` -> `{t['status']}`\n"

            return {"response": text, "mode": "semantic_nlq", "data": data}

        # Standart yordamchi javob
        return {
            "response": (
                "👋 Assalomu alaykum! Men **Avtosalon va Mashina Arendasi AI Boshqaruv Maslahatchisi**man.\n\n"
                "Quyidagi savollar bo'yicha yordam bera olaman:\n"
                "- 💰 *\"Bu oy qancha foyda qildik?\"* yoki *\"Oylik tushum qancha?\"*\n"
                "- ⚠️ *\"Kimlarni arendadan qarzi bor?\"* yoki *\"Qarzdorlar ro'yxatini ber\"*\n"
                "- 📊 *\"Executive summary hisobotini tayyorla\"*\n"
                "- 🚗 *\"Salonda qanday mashinalar bor?\"* yoki *\"Tracker haqida ma'lumot ber\"*\n"
                "- 🔔 *\"Qarzdorlarga eslatma jo'nat\"*"
            ),
            "mode": "semantic_nlq"
        }

agent_instance = AIAgent()
