// Baraka Avto AI CRM & ERP Frontend Logic

let currentTab = 'dashboard';
let allCars = [];
let revenueChart = null;

// Currency formatter
function formatUzs(amount) {
    if (amount === undefined || amount === null) return "0 so'm";
    return Number(amount).toLocaleString('uz-UZ') + " so'm";
}

// 1. INITIALIZATION & TAB SWITCHING
document.addEventListener("DOMContentLoaded", () => {
    initChart();
    loadDashboardAnalytics();
    loadCars();
    loadSalesContracts();
    loadRentals();
    loadLedger();
    loadDebtors();
});

function switchTab(tabName) {
    currentTab = tabName;

    // Hide all tabs
    ['dashboard', 'inventory', 'sales', 'rentals', 'transactions', 'debtors'].forEach(t => {
        const el = document.getElementById(`tab-${t}`);
        const btn = document.getElementById(`nav-${t}`);
        if (el) el.classList.add('hidden');
        if (btn) {
            btn.classList.remove('bg-indigo-600', 'text-white', 'shadow');
            btn.classList.add('text-slate-400');
        }
    });

    // Show active tab
    const activeEl = document.getElementById(`tab-${tabName}`);
    const activeBtn = document.getElementById(`nav-${tabName}`);
    if (activeEl) activeEl.classList.remove('hidden');
    if (activeBtn) {
        activeBtn.classList.add('bg-indigo-600', 'text-white', 'shadow');
        activeBtn.classList.remove('text-slate-400');
    }

    // Refresh data if needed
    if (tabName === 'dashboard') loadDashboardAnalytics();
    if (tabName === 'inventory') loadCars();
    if (tabName === 'sales') loadSalesContracts();
    if (tabName === 'rentals') loadRentals();
    if (tabName === 'transactions') loadLedger();
    if (tabName === 'debtors') loadDebtors();
}

// 2. DASHBOARD & CHART LOGIC
function initChart() {
    const ctx = document.getElementById('revenueChart').getContext('2d');
    revenueChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Naqd Sotuv', 'Bo\'lib To\'lash (Down Payment)', 'Bo\'lib To\'lash (Oylik)', 'Ijara (Arenda)'],
            datasets: [{
                label: 'Tushum (so\'m)',
                data: [0, 0, 0, 0],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.7)',
                    'rgba(99, 102, 241, 0.7)',
                    'rgba(139, 92, 246, 0.7)',
                    'rgba(6, 182, 212, 0.7)'
                ],
                borderColor: [
                    '#10b981',
                    '#6366f1',
                    '#8b5cf6',
                    '#06b6d4'
                ],
                borderWidth: 1.5,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8', font: { size: 10 } }
                },
                y: {
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8', font: { size: 10 } }
                }
            }
        }
    });
}

async function loadDashboardAnalytics() {
    try {
        const [revRes, fleetRes, debtRes] = await Promise.all([
            fetch('/api/analytics/monthly-revenue'),
            fetch('/api/analytics/fleet'),
            fetch('/api/analytics/debtors')
        ]);

        const rev = await revRes.json();
        const fleet = await fleetRes.json();
        const debtors = await debtRes.json();

        // Update KPIs
        const mRev = rev.month_revenue;
        document.getElementById('kpi-month-rev').innerText = formatUzs(mRev.total_month_revenue_uzs);
        document.getElementById('kpi-fleet-stats').innerText = `${fleet.total_cars_in_system} ta mashina`;
        document.getElementById('kpi-fleet-sub').innerText = `Salonda: ${fleet.available_in_showroom} | Sotilgan: ${fleet.total_sold_cars}`;
        document.getElementById('kpi-active-rentals').innerText = `${fleet.active_rentals_count} ta`;
        document.getElementById('kpi-utilization').innerText = `Park bandligi: ${fleet.fleet_utilization_rate_pct}%`;

        const totalDebt = debtors.reduce((sum, d) => sum + (d.total_debt_uzs || 0), 0);
        document.getElementById('kpi-overdue-debt').innerText = formatUzs(totalDebt);
        document.getElementById('kpi-debtors-count').innerText = `${debtors.length} nafar qarzdor`;

        const badge = document.getElementById('nav-debtor-badge');
        if (debtors.length > 0) {
            badge.innerText = debtors.length;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }

        // Sub revenue numbers
        document.getElementById('sub-cash-rev').innerText = formatUzs(mRev.cash_sales_uzs);
        document.getElementById('sub-inst-rev').innerText = formatUzs(mRev.total_installment_revenue_uzs);
        document.getElementById('sub-rent-rev').innerText = formatUzs(mRev.rental_collections_uzs);

        // Update Chart
        if (revenueChart) {
            revenueChart.data.datasets[0].data = [
                mRev.cash_sales_uzs,
                mRev.installment_down_payments_uzs,
                mRev.installment_monthly_collections_uzs,
                mRev.rental_collections_uzs
            ];
            revenueChart.update();
        }
    } catch (e) {
        console.error("Dashboard yuklashda xatolik:", e);
    }
}

// 3. INVENTORY MANAGEMENT
async function loadCars(status = 'ALL') {
    try {
        const url = status && status !== 'ALL' ? `/api/cars?status=${status}` : '/api/cars';
        const res = await fetch(url);
        allCars = await res.json();
        renderCarsGrid(allCars);
        populateCarSelects(allCars);
    } catch (e) {
        console.error("Mashinalar yuklanmadi:", e);
    }
}

function renderCarsGrid(cars) {
    const grid = document.getElementById('cars-grid');
    if (!cars || cars.length === 0) {
        grid.innerHTML = `<div class="col-span-3 text-center py-12 text-slate-500 text-sm">Avtomobil topilmadi.</div>`;
        return;
    }

    grid.innerHTML = cars.map(c => {
        let badgeColor = "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
        let statusLabel = "Sotuvda (Available)";
        if (c.status === 'Rented') {
            badgeColor = "bg-cyan-500/20 text-cyan-400 border-cyan-500/30";
            statusLabel = "Arendada (Rented)";
        } else if (c.status === 'Sold_Cash') {
            badgeColor = "bg-purple-500/20 text-purple-400 border-purple-500/30";
            statusLabel = "Naqd Sotilgan";
        } else if (c.status === 'Sold_Installment') {
            badgeColor = "bg-amber-500/20 text-amber-400 border-amber-500/30";
            statusLabel = "Bo'lib To'lashda";
        }

        const img = c.image_url || "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80";

        return `
            <div class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl overflow-hidden transition shadow-lg flex flex-col">
                <div class="h-44 w-full relative overflow-hidden bg-slate-800">
                    <img src="${img}" alt="${c.model}" class="w-full h-full object-cover">
                    <span class="absolute top-3 right-3 text-[11px] font-semibold px-2.5 py-0.5 rounded-full border backdrop-blur-md ${badgeColor}">
                        ${statusLabel}
                    </span>
                    <span class="absolute bottom-3 left-3 text-[11px] font-bold px-2 py-0.5 rounded bg-black/70 text-white backdrop-blur">
                        ${c.plate_number || 'Tranzit'}
                    </span>
                </div>
                <div class="p-4 flex-1 flex flex-col justify-between space-y-3">
                    <div>
                        <h4 class="font-bold text-sm text-white">${c.model}</h4>
                        <p class="text-[11px] text-slate-400 mt-0.5">VIN: <code class="text-slate-300 font-mono">${c.vin}</code> | ${c.year}-yil</p>
                    </div>

                    <div class="grid grid-cols-2 gap-2 text-[11px] bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                        <div>
                            <span class="text-slate-400">Sotuv narxi:</span>
                            <p class="font-bold text-indigo-400 text-xs">${formatUzs(c.sale_price_uzs)}</p>
                            <p class="text-[10px] text-slate-500">$${c.sale_price_usd.toLocaleString()}</p>
                        </div>
                        <div>
                            <span class="text-slate-400">Oylik arenda:</span>
                            <p class="font-bold text-cyan-400 text-xs">${formatUzs(c.rental_price_monthly_uzs)}</p>
                            <p class="text-[10px] text-slate-500">$${c.rental_price_monthly_usd}/oy</p>
                        </div>
                    </div>

                    <div class="flex items-center justify-between text-[11px] pt-1 border-t border-slate-800/80">
                        <span class="text-slate-400"><i class="fa-solid fa-gas-pump mr-1"></i>${c.fuel_type}</span>
                        <span class="text-slate-400"><i class="fa-solid fa-gear mr-1"></i>${c.transmission}</span>
                        <button onclick="askAIAboutCar('${c.plate_number || c.model}')" class="text-indigo-400 hover:text-indigo-300 font-medium">
                            AI Tahlil &rarr;
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function filterCars(status) {
    document.querySelectorAll('.car-filter-btn').forEach(btn => {
        if (btn.getAttribute('data-status') === status) {
            btn.classList.add('bg-indigo-600', 'text-white');
            btn.classList.remove('bg-slate-800', 'text-slate-300');
        } else {
            btn.classList.remove('bg-indigo-600', 'text-white');
            btn.classList.add('bg-slate-800', 'text-slate-300');
        }
    });
    loadCars(status);
}

function searchCars(term) {
    if (!term) {
        renderCarsGrid(allCars);
        return;
    }
    const filtered = allCars.filter(c => 
        c.model.toLowerCase().includes(term.toLowerCase()) ||
        c.vin.toLowerCase().includes(term.toLowerCase()) ||
        (c.plate_number && c.plate_number.toLowerCase().includes(term.toLowerCase()))
    );
    renderCarsGrid(filtered);
}

function populateCarSelects(cars) {
    const available = cars.filter(c => c.status === 'Available');
    const options = available.map(c => `<option value="${c.id}">${c.model} (${c.plate_number || 'Tranzit'}) - ${formatUzs(c.sale_price_uzs)}</option>`).join('');
    
    const cashSel = document.getElementById('cash-car-id');
    const instSel = document.getElementById('inst-car-id');
    const rentSel = document.getElementById('rent-car-id');

    if (cashSel) cashSel.innerHTML = options || '<option disabled>Mavjud bo\'sh mashina yo\'q</option>';
    if (instSel) instSel.innerHTML = options || '<option disabled>Mavjud bo\'sh mashina yo\'q</option>';
    if (rentSel) rentSel.innerHTML = options || '<option disabled>Mavjud bo\'sh mashina yo\'q</option>';
}

// 4. SALES CONTRACTS & AMORTIZATION SCHEDULE
async function loadSalesContracts() {
    try {
        const res = await fetch('/api/payments/ledger?limit=100');
        const ledger = await res.json();
        const tbody = document.getElementById('sales-contracts-table-body');

        // Extract unique contracts
        const contractsMap = {};
        ledger.forEach(item => {
            if (item.contract_type === 'SALE_INSTALLMENT' && !contractsMap[item.contract_id]) {
                contractsMap[item.contract_id] = item;
            }
        });

        // Also fetch from cars with active installment contracts
        const instContracts = Object.values(contractsMap);
        if (instContracts.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-slate-500">Bo'lib to'lash shartnomalari topilmadi.</td></tr>`;
            return;
        }

        tbody.innerHTML = instContracts.map(c => `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="py-3 px-3 font-mono font-medium text-indigo-400">${c.contract_id}</td>
                <td class="py-3 px-3 font-medium text-white">${c.customer_name}<br><span class="text-[10px] text-slate-400">${c.customer_phone}</span></td>
                <td class="py-3 px-3">${c.car_model}<br><span class="text-[10px] font-mono text-slate-400">${c.plate_number || ''}</span></td>
                <td class="py-3 px-3 font-semibold text-white">${formatUzs(c.amount_uzs * 20)}</td>
                <td class="py-3 px-3 text-emerald-400 font-medium">${formatUzs(c.amount_uzs * 5)}</td>
                <td class="py-3 px-3 text-rose-400 font-medium">${formatUzs(c.remaining_balance_uzs || 0)}</td>
                <td class="py-3 px-3 font-medium text-slate-200">${formatUzs(c.amount_uzs)}</td>
                <td class="py-3 px-3 text-center">
                    <button onclick="viewAmortizationSchedule('${c.contract_id}', '${c.car_model}')" class="bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white px-2.5 py-1 rounded text-[11px] font-medium transition">
                        <i class="fa-solid fa-calendar-days mr-1"></i> Grafik
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        console.error("Sotuv shartnomalari yuklanmadi:", e);
    }
}

async function viewAmortizationSchedule(contractId, carModel) {
    try {
        const res = await fetch(`/api/sales/contracts/${contractId}/schedule`);
        const schedule = await res.json();
        
        document.getElementById('schedule-modal-title').innerText = `${carModel} — To'lovlar Grafigi (${contractId})`;
        const tbody = document.getElementById('schedule-table-body');

        tbody.innerHTML = schedule.map(s => {
            let statusBadge = `<span class="bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded text-[10px] font-semibold">Kutilmoqda (PENDING)</span>`;
            let payBtn = `<button onclick="quickPay('${contractId}', ${s.amount_due_uzs}, ${s.id})" class="bg-emerald-600/30 hover:bg-emerald-600 text-emerald-300 hover:text-white px-2.5 py-1 rounded text-[10px] font-medium transition"><i class="fa-solid fa-check mr-1"></i> To'lash</button>`;

            if (s.status === 'PAID') {
                statusBadge = `<span class="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded text-[10px] font-semibold">To'langan (PAID)</span>`;
                payBtn = `<span class="text-emerald-500 text-[11px] font-semibold"><i class="fa-solid fa-circle-check"></i> To'langan</span>`;
            } else if (s.status === 'OVERDUE') {
                statusBadge = `<span class="bg-rose-500/20 text-rose-400 border border-rose-500/30 px-2 py-0.5 rounded text-[10px] font-semibold">Kechikkan (OVERDUE)</span>`;
            }

            return `
                <tr class="hover:bg-slate-800/40 transition">
                    <td class="py-2.5 px-3 font-semibold text-slate-400">${s.installment_no}-oy</td>
                    <td class="py-2.5 px-3 font-mono">${s.due_date}</td>
                    <td class="py-2.5 px-3 font-bold text-white">${formatUzs(s.amount_due_uzs)}</td>
                    <td class="py-2.5 px-3">${statusBadge}</td>
                    <td class="py-2.5 px-3 text-slate-400 text-[10px]">${s.paid_at || '-'}</td>
                    <td class="py-2.5 px-3 text-center">${payBtn}</td>
                </tr>
            `;
        }).join('');

        openModal('modal-schedule');
    } catch (e) {
        alert("Grafikni yuklashda xatolik: " + e.message);
    }
}

// 5. RENTALS MANAGEMENT
async function loadRentals() {
    try {
        const res = await fetch('/api/rentals/active');
        const rentals = await res.json();
        const tbody = document.getElementById('rentals-table-body');

        if (!rentals || rentals.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-slate-500">Arendadagi faol mashinalar mavjud emas.</td></tr>`;
            return;
        }

        tbody.innerHTML = rentals.map(r => {
            let statusColor = "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
            let statusText = "Amalda";
            if (r.is_expired) {
                statusColor = "text-rose-400 bg-rose-500/10 border-rose-500/20";
                statusText = "Muddati O'tgan";
            } else if (r.is_expiring_soon) {
                statusColor = "text-amber-400 bg-amber-500/10 border-amber-500/20";
                statusText = "Muddati Tugamoqda";
            }

            return `
                <tr class="hover:bg-slate-800/40 transition">
                    <td class="py-3 px-3 font-mono font-medium text-cyan-400">${r.contract_id}</td>
                    <td class="py-3 px-3 font-medium text-white">${r.customer_name}<br><span class="text-[10px] text-slate-400">${r.customer_phone}</span></td>
                    <td class="py-3 px-3 font-medium">${r.car_model}<br><span class="text-[10px] font-mono text-slate-400">${r.plate_number || ''}</span></td>
                    <td class="py-3 px-3 text-slate-300 font-mono text-[11px]">${r.start_date} &rarr; ${r.end_date}</td>
                    <td class="py-3 px-3 font-bold text-white">${formatUzs(r.monthly_payment_uzs)}</td>
                    <td class="py-3 px-3 font-bold ${r.days_left < 5 ? 'text-rose-400' : 'text-slate-200'}">${r.days_left} kun qoldi</td>
                    <td class="py-3 px-3"><span class="px-2 py-0.5 rounded text-[10px] font-semibold border ${statusColor}">${statusText}</span></td>
                    <td class="py-3 px-3 text-center">
                        <button onclick="preparePayment('${r.contract_id}', ${r.monthly_payment_uzs})" class="bg-cyan-600/30 hover:bg-cyan-600 text-cyan-300 hover:text-white px-2.5 py-1 rounded text-[10px] font-medium transition">
                            <i class="fa-solid fa-dollar-sign mr-1"></i> To'lov
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.error("Ijara ro'yxatini yuklashda xatolik:", e);
    }
}

// 6. TRANSACTIONS & LEDGER (REQUIREMENT 4: VEHICLE SNAPSHOT)
async function loadLedger() {
    try {
        const res = await fetch('/api/payments/ledger?limit=50');
        const ledger = await res.json();
        const tbody = document.getElementById('ledger-table-body');

        if (!ledger || ledger.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-6 text-slate-500">Tranzaksiyalar mavjud emas.</td></tr>`;
            return;
        }

        tbody.innerHTML = ledger.map(l => `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="py-3 px-3 font-mono font-medium text-indigo-400">${l.transaction_code}</td>
                <td class="py-3 px-3 text-[11px] text-slate-400 font-mono">${l.payment_date}</td>
                <td class="py-3 px-3 font-medium text-white">${l.customer_name}</td>
                <td class="py-3 px-3">${l.car_model} <span class="text-[10px] font-mono text-slate-400">(${l.plate_number || 'Tranzit'})</span></td>
                <td class="py-3 px-3"><span class="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-800 text-slate-300">${l.payment_category}</span></td>
                <td class="py-3 px-3 text-slate-400">${l.payment_method}</td>
                <td class="py-3 px-3 text-right font-bold text-emerald-400">${formatUzs(l.amount_uzs)}</td>
            </tr>
        `).join('');
    } catch (e) {
        console.error("Ledger yuklashda xatolik:", e);
    }
}

async function handlePaymentSubmit(e) {
    e.preventDefault();
    const contractId = document.getElementById('pay-contract-id').value.trim();
    const amount = parseFloat(document.getElementById('pay-amount').value);
    const method = document.getElementById('pay-method').value;

    try {
        const res = await fetch('/api/payments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contract_id: contractId,
                amount_uzs: amount,
                payment_method: method
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "To'lovni qayd etishda xatolik");

        // REQUIREMENT 4: Show full vehicle and customer snapshot modal immediately!
        showVehicleSnapshotModal(data);

        // Refresh tables
        loadLedger();
        loadDashboardAnalytics();
        loadDebtors();
        loadSalesContracts();
        loadRentals();

        // Reset form
        document.getElementById('pay-contract-id').value = '';
        document.getElementById('pay-amount').value = '';
    } catch (err) {
        alert("Xatolik: " + err.message);
    }
}

function quickPay(contractId, amount, scheduleId) {
    closeModal('modal-schedule');
    switchTab('transactions');
    document.getElementById('pay-contract-id').value = contractId;
    document.getElementById('pay-amount').value = amount;
}

function preparePayment(contractId, amount) {
    switchTab('transactions');
    document.getElementById('pay-contract-id').value = contractId;
    document.getElementById('pay-amount').value = amount;
}

// REQUIREMENT 4: VEHICLE SNAPSHOT MODAL DISPLAY
function showVehicleSnapshotModal(data) {
    const v = data.vehicle_and_customer_details;
    const t = data.transaction;

    const body = document.getElementById('snapshot-body');
    body.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-950 p-4 rounded-2xl border border-slate-800">
            <div class="space-y-2">
                <span class="text-[10px] uppercase font-bold text-slate-400">Avtomobil Ma'lumotlari</span>
                <div class="flex items-center gap-3">
                    <img src="${v.image_url || 'https://images.unsplash.com/photo-1549399542-7e3f8b79c341'}" class="w-16 h-12 object-cover rounded-lg border border-slate-700">
                    <div>
                        <h4 class="font-bold text-sm text-white">${v.model}</h4>
                        <p class="text-[11px] text-indigo-400 font-mono">${v.plate_number || 'Tranzit'}</p>
                    </div>
                </div>
                <div class="space-y-1 text-slate-300 pt-1">
                    <p><span class="text-slate-400">VIN:</span> <code class="font-mono text-white">${v.vin}</code></p>
                    <p><span class="text-slate-400">Yili / Rangi:</span> ${v.year}-yil, ${v.color}</p>
                    <p><span class="text-slate-400">Holati:</span> <span class="text-emerald-400 font-semibold">${v.car_status}</span></p>
                </div>
            </div>

            <div class="space-y-2">
                <span class="text-[10px] uppercase font-bold text-slate-400">Mijoz va Shartnoma</span>
                <h4 class="font-bold text-sm text-white">${v.customer_name}</h4>
                <div class="space-y-1 text-slate-300">
                    <p><span class="text-slate-400">Telefon:</span> ${v.customer_phone}</p>
                    <p><span class="text-slate-400">Manzil:</span> ${v.customer_address || "Ko'rsatilmagan"}</p>
                    <p><span class="text-slate-400">Shartnoma ID:</span> <span class="font-mono text-cyan-400">${v.contract_id}</span> (${v.contract_type})</p>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-slate-800/40 p-3 rounded-2xl text-center">
            <div class="bg-slate-900/80 p-2.5 rounded-xl border border-slate-700/50">
                <span class="text-slate-400 text-[10px]">Qabul Qilingan To'lov</span>
                <p class="font-bold text-emerald-400 text-xs mt-0.5">+${formatUzs(t.amount_uzs)}</p>
            </div>
            <div class="bg-slate-900/80 p-2.5 rounded-xl border border-slate-700/50">
                <span class="text-slate-400 text-[10px]">Jami To'langan</span>
                <p class="font-bold text-white text-xs mt-0.5">${formatUzs(v.total_paid_uzs)}</p>
            </div>
            <div class="bg-slate-900/80 p-2.5 rounded-xl border border-slate-700/50">
                <span class="text-slate-400 text-[10px]">Qoldiq Qarz</span>
                <p class="font-bold text-rose-400 text-xs mt-0.5">${formatUzs(v.remaining_debt_uzs)}</p>
            </div>
            <div class="bg-slate-900/80 p-2.5 rounded-xl border border-slate-700/50">
                <span class="text-slate-400 text-[10px]">Navbatdagi To'lov Sanasi</span>
                <p class="font-bold text-indigo-400 text-xs mt-0.5">${v.next_payment_due_date}</p>
            </div>
        </div>
    `;

    openModal('modal-vehicle-snapshot');
}

// 7. DEBTORS SURVEILLANCE & ALERTS
async function loadDebtors() {
    try {
        const res = await fetch('/api/analytics/debtors');
        const debtors = await res.json();
        const container = document.getElementById('debtors-container');

        if (!debtors || debtors.length === 0) {
            container.innerHTML = `
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center space-y-2">
                    <i class="fa-solid fa-circle-check text-emerald-400 text-3xl"></i>
                    <h4 class="font-bold text-sm text-white">Muddati o'tgan qarzdorlar yo'q!</h4>
                    <p class="text-xs text-slate-400">Barcha mijozlar to'lovlarni o'z vaqtida amalga oshirgan.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = debtors.map(d => `
            <div class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition shadow-md">
                <div class="flex items-start gap-3.5">
                    <div class="w-10 h-10 rounded-xl bg-rose-500/10 text-rose-400 flex items-center justify-center shrink-0 mt-0.5">
                        <i class="fa-solid fa-user-xmark"></i>
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h4 class="font-bold text-sm text-white">${d.customer_name}</h4>
                            <span class="text-[10px] font-semibold px-2 py-0.2 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30">
                                ${d.days_overdue} kun kechikkan
                            </span>
                            <span class="text-[10px] text-slate-400 font-mono">${d.contract_type}</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-0.5">
                            Telefon: <strong class="text-slate-200">${d.customer_phone}</strong> | 
                            Avto: <strong class="text-slate-200">${d.car_model} (${d.plate_number || 'Raqamsiz'})</strong>
                        </p>
                        <p class="text-[11px] text-slate-400 mt-1">
                            Shartnoma: <code class="text-indigo-400 font-mono">${d.contract_id}</code> | 
                            Oylik badal: ${formatUzs(d.monthly_payment_uzs)}
                        </p>
                    </div>
                </div>

                <div class="flex sm:flex-col items-center sm:items-end justify-between gap-2 border-t sm:border-t-0 pt-2 sm:pt-0 border-slate-800">
                    <div class="text-right">
                        <span class="text-[10px] text-slate-400">Jami Kechikkan Qarz:</span>
                        <p class="font-bold text-rose-400 text-sm">${formatUzs(d.total_debt_uzs)}</p>
                        ${d.total_penalty_uzs > 0 ? `<p class="text-[10px] text-amber-400">Jarima: +${formatUzs(d.total_penalty_uzs)}</p>` : ''}
                    </div>
                    <div class="flex gap-2">
                        <button onclick="triggerSingleReminder('${d.contract_id}', '${d.customer_name}')" class="bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition">
                            <i class="fa-solid fa-paper-plane text-xs"></i> Eslatma SMS
                        </button>
                        <button onclick="preparePayment('${d.contract_id}', ${d.total_debt_uzs})" class="bg-emerald-600/30 hover:bg-emerald-600 text-emerald-300 hover:text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition">
                            To'lov
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error("Qarzdorlarni yuklashda xatolik:", e);
    }
}

async function triggerSingleReminder(contractId, name) {
    try {
        const res = await fetch(`/api/ai/check-reminders?contract_id=${contractId}`, { method: 'POST' });
        const data = await res.json();
        alert(`✅ ${name} uchun to'lov eslatmasi Telegram/SMS orqali yuborildi!`);
    } catch (e) {
        alert("Eslatma yuborishda xatolik: " + e.message);
    }
}

async function triggerAllReminders() {
    try {
        const res = await fetch('/api/ai/check-reminders', { method: 'POST' });
        const data = await res.json();
        alert(`✅ Barcha ${data.yuborilgan_bildirishnomalar_soni} nafar qarzdorga avtomatlashtirilgan ogohlantirish eslatmalari yuborildi!`);
    } catch (e) {
        alert("Eslatmalar yuborishda xatolik: " + e.message);
    }
}

// 8. AI COPILOT CHAT LOGIC
async function handleChatSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('ai-chat-input');
    const msg = input.value.trim();
    if (!msg) return;

    appendChatMessage('user', msg);
    input.value = '';
    sendAiMessage(msg);
}

function sendQuickPrompt(promptText) {
    appendChatMessage('user', promptText);
    sendAiMessage(promptText);
}

function askAIAboutCar(identifier) {
    switchTab('dashboard');
    const prompt = `${identifier} avtomobili haqida to'liq ma'lumot ber`;
    sendQuickPrompt(prompt);
}

async function sendAiMessage(message) {
    const sendBtn = document.getElementById('ai-send-btn');
    sendBtn.disabled = true;
    sendBtn.innerHTML = `<i class="fa-solid fa-spinner animate-spin"></i>`;

    // Append loading placeholder
    const loadingId = 'ai-loading-' + Date.now();
    appendLoadingMessage(loadingId);

    try {
        const res = await fetch('/api/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });
        const data = await res.json();

        // Remove loading
        const loader = document.getElementById(loadingId);
        if (loader) loader.remove();

        appendChatMessage('assistant', data.response);
    } catch (err) {
        const loader = document.getElementById(loadingId);
        if (loader) loader.remove();
        appendChatMessage('assistant', `⚠️ Kechirasiz, xatolik yuz berdi: ${err.message}`);
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = `<i class="fa-solid fa-paper-plane"></i>`;
    }
}

function appendChatMessage(role, text) {
    const container = document.getElementById('ai-chat-messages');
    const isUser = role === 'user';
    const parsedHtml = marked.parse(text);

    const div = document.createElement('div');
    div.className = `flex gap-2.5 items-start ${isUser ? 'flex-row-reverse' : ''}`;
    div.innerHTML = `
        <div class="w-6 h-6 rounded-md ${isUser ? 'bg-indigo-600 text-white' : 'bg-indigo-600/30 text-indigo-400'} flex items-center justify-center shrink-0 mt-0.5">
            <i class="fa-solid ${isUser ? 'fa-user' : 'fa-robot'} text-xs"></i>
        </div>
        <div class="${isUser ? 'bg-indigo-600 text-white' : 'bg-slate-800/90 text-slate-200 border border-slate-700/60'} p-3 rounded-2xl ${isUser ? 'rounded-tr-sm' : 'rounded-tl-sm'} leading-relaxed shadow-sm max-w-[90%] markdown-body">
            ${parsedHtml}
        </div>
    `;

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function appendLoadingMessage(id) {
    const container = document.getElementById('ai-chat-messages');
    const div = document.createElement('div');
    div.id = id;
    div.className = `flex gap-2.5 items-start`;
    div.innerHTML = `
        <div class="w-6 h-6 rounded-md bg-indigo-600/30 text-indigo-400 flex items-center justify-center shrink-0 mt-0.5">
            <i class="fa-solid fa-robot text-xs"></i>
        </div>
        <div class="bg-slate-800/90 text-slate-400 p-3 rounded-2xl rounded-tl-sm border border-slate-700/60 flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-indigo-500 animate-ping"></span> Tahlil qilinmoqda...
        </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function clearChat() {
    document.getElementById('ai-chat-messages').innerHTML = `
        <div class="flex gap-2.5 items-start">
            <div class="w-6 h-6 rounded-md bg-indigo-600/30 text-indigo-400 flex items-center justify-center shrink-0 mt-0.5">
                <i class="fa-solid fa-robot text-xs"></i>
            </div>
            <div class="bg-slate-800/90 text-slate-200 p-3 rounded-2xl rounded-tl-sm border border-slate-700/60 leading-relaxed shadow-sm max-w-[90%]">
                Assalomu alaykum! Suhbat tozalandi. Savolingizni berishingiz mumkin.
            </div>
        </div>
    `;
}

// 9. FORM SUBMITS (CASH, INSTALLMENT, RENTAL, NEW CAR)
async function handleCashSaleSubmit(e) {
    e.preventDefault();
    const carId = document.getElementById('cash-car-id').value;
    const name = document.getElementById('cash-cust-name').value;
    const phone = document.getElementById('cash-cust-phone').value;
    const method = document.getElementById('cash-pay-method').value;

    try {
        const res = await fetch('/api/sales/cash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                car_id: carId,
                customer: { full_name: name, phone: phone },
                payment_method: method
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Naqd sotuvda xatolik");

        closeModal('modal-cash-sale');
        alert(`✅ ${data.car_model} naqd to'lov bilan muvaffaqiyatli sotildi! Tranzaksiya: ${data.transaction_code}`);
        loadCars();
        loadDashboardAnalytics();
        loadLedger();
    } catch (err) {
        alert("Xatolik: " + err.message);
    }
}

async function handleInstallmentSubmit(e) {
    e.preventDefault();
    const carId = document.getElementById('inst-car-id').value;
    const name = document.getElementById('inst-cust-name').value;
    const phone = document.getElementById('inst-cust-phone').value;
    const downPayment = parseFloat(document.getElementById('inst-down-payment').value);
    const months = parseInt(document.getElementById('inst-months').value);

    try {
        const res = await fetch('/api/sales/installment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                car_id: carId,
                customer: { full_name: name, phone: phone },
                down_payment_uzs: downPayment,
                term_months: months
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Muddatli to'lovda xatolik");

        closeModal('modal-installment');
        alert(`✅ ${data.car_model} ${months} oyga bo'lib to'lashga rasmiylashtirildi! Shartnoma: ${data.contract_id}`);
        loadCars();
        loadSalesContracts();
        loadDashboardAnalytics();
        loadLedger();
    } catch (err) {
        alert("Xatolik: " + err.message);
    }
}

async function handleRentalSubmit(e) {
    e.preventDefault();
    const carId = document.getElementById('rent-car-id').value;
    const name = document.getElementById('rent-cust-name').value;
    const phone = document.getElementById('rent-cust-phone').value;
    const months = parseInt(document.getElementById('rent-months').value);
    const deposit = parseFloat(document.getElementById('rent-deposit').value) || 0;

    try {
        const res = await fetch('/api/rentals', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                car_id: carId,
                customer: { full_name: name, phone: phone },
                term_months: months,
                deposit_uzs: deposit
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Ijara rasmiylashtirishda xatolik");

        closeModal('modal-rental');
        alert(`✅ ${data.car_model} ${months} oy muddatga ijaraga topshirildi! Shartnoma: ${data.contract_id}`);
        loadCars();
        loadRentals();
        loadDashboardAnalytics();
        loadLedger();
    } catch (err) {
        alert("Xatolik: " + err.message);
    }
}

async function handleAddCarSubmit(e) {
    e.preventDefault();
    const car = {
        model: document.getElementById('add-model').value,
        year: parseInt(document.getElementById('add-year').value),
        vin: document.getElementById('add-vin').value,
        plate_number: document.getElementById('add-plate').value,
        color: document.getElementById('add-color').value,
        purchase_price_usd: parseFloat(document.getElementById('add-purchase-usd').value),
        sale_price_usd: parseFloat(document.getElementById('add-sale-usd').value),
        sale_price_uzs: parseFloat(document.getElementById('add-sale-uzs').value),
        rental_price_monthly_uzs: parseFloat(document.getElementById('add-rent-uzs').value),
        image_url: document.getElementById('add-img').value
    };

    try {
        const res = await fetch('/api/cars', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(car)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Mashina qo'shishda xatolik");

        closeModal('modal-add-car');
        alert(`✅ ${data.model} inventar bazasiga muvaffaqiyatli qo'shildi!`);
        loadCars();
        loadDashboardAnalytics();
    } catch (err) {
        alert("Xatolik: " + err.message);
    }
}

// MODAL HELPERS
function openModal(id) { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }
function openNewCarModal() { openModal('modal-add-car'); }
function openCashSaleModal() { openModal('modal-cash-sale'); }
function openInstallmentModal() { openModal('modal-installment'); }
function openRentalModal() { openModal('modal-rental'); }
