from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class CarCreate(BaseModel):
    id: Optional[str] = None
    model: str
    make: str = "Chevrolet"
    year: int
    vin: str
    plate_number: Optional[str] = None
    color: str = "Oq"
    mileage: int = 0
    fuel_type: str = "Benzin"
    transmission: str = "Avtomat"
    purchase_price_usd: float
    sale_price_usd: float
    sale_price_uzs: float
    rental_price_daily_usd: float = 35.0
    rental_price_monthly_usd: float = 650.0
    rental_price_monthly_uzs: float = 8250000.0
    condition: str = "A'lo"
    image_url: Optional[str] = None
    description: Optional[str] = None

class CustomerInput(BaseModel):
    full_name: str
    phone: str
    passport_series: Optional[str] = None
    pinfl: Optional[str] = None
    address: Optional[str] = None

class CashSaleRequest(BaseModel):
    car_id: str
    customer: CustomerInput
    actual_sale_price_uzs: Optional[float] = None
    payment_method: str = "BANK_TRANSFER"  # CASH, CLICK, PAYME, UZUM, BANK_TRANSFER
    notes: Optional[str] = "Naqd to'liq sotuv"

class InstallmentSaleRequest(BaseModel):
    car_id: str
    customer: CustomerInput
    down_payment_uzs: float
    term_months: int = 24  # 12, 18, 24, 36 oy
    annual_markup_percent: float = 24.0
    payment_method: str = "BANK_TRANSFER"
    notes: Optional[str] = "Bo'lib to'lash shartnomasi"

class RentalRequest(BaseModel):
    car_id: str
    customer: CustomerInput
    term_months: int = 1
    monthly_rate_uzs: Optional[float] = None
    deposit_uzs: float = 0.0
    payment_method: str = "CLICK"
    notes: Optional[str] = "Avtomobil ijarasi"

class PaymentRecordRequest(BaseModel):
    contract_id: str
    amount_uzs: float
    payment_method: str = "CLICK"  # CASH, CLICK, PAYME, UZUM, BANK_TRANSFER
    payment_category: Optional[str] = None # INSTALLMENT_MONTHLY, RENTAL_MONTHLY, etc.
    schedule_id: Optional[int] = None
    reference_no: Optional[str] = None
    notes: Optional[str] = None

class AIChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default_session"
