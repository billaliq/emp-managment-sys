/**
 * LoanView.js — DOM rendering layer for Loans (MVC View)
 */

import { BaseView } from '../core/BaseView.js';
import { escapeHtml } from '../core/Utils.js';

export class LoanView extends BaseView {
    constructor() {
        super();
        this.loanModal       = document.getElementById('newLoanModal');
        this.repaymentModal  = document.getElementById('addRepaymentModal');
        this.poolModal       = document.getElementById('loanPoolModal');
        this.loanForm        = document.getElementById('loanForm');
        this.repaymentForm   = document.getElementById('repaymentForm');
        this.poolForm        = document.getElementById('poolForm');
        this.tabs            = document.querySelectorAll('.tab');
        this.tabContents     = {
            loans:      document.getElementById('loansTab'),
            pending:    document.getElementById('pendingTab'),
            repayments: document.getElementById('repaymentsTab'),
            report:     document.getElementById('reportTab'),
        };
    }

    // ── Tabs ─────────────────────────────────────
    activateTab(tabName) {
        this.tabs.forEach(t => { t.classList.remove('active'); t.style.transform = 'translateY(0)'; });
        Object.values(this.tabContents).forEach(c => { if (c) { c.classList.remove('active'); c.style.display = 'none'; } });
        const tab = document.querySelector(`.tab[data-tab="${tabName}"]`);
        const content = this.tabContents[tabName];
        if (tab)     { tab.classList.add('active'); tab.style.transform = 'translateY(-2px)'; }
        if (content) {
            content.style.display = 'block';
            setTimeout(() => content.classList.add('active'), 50);
        }
    }

    // ── Modals ───────────────────────────────────
    openLoanModal()      { this.loanModal      && (this.loanModal.style.display      = 'flex'); }
    closeLoanModal()     { this.loanModal      && (this.loanModal.style.display      = 'none'); }
    openRepaymentModal() { this.repaymentModal && (this.repaymentModal.style.display = 'flex'); }
    closeRepaymentModal(){ this.repaymentModal && (this.repaymentModal.style.display = 'none'); }
    openPoolModal()      { this.poolModal      && (this.poolModal.style.display      = 'flex'); }
    closePoolModal()     { this.poolModal      && (this.poolModal.style.display      = 'none'); }

    // ── Loan details modal (dynamic) ─────────────
    showLoanDetailsModal(loan) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'flex';
        modal.innerHTML = `
            <div class="modal-content" style="max-width:700px;">
                <div class="modal-header">
                    <h2 class="modal-title">Loan Details</h2>
                    <button class="close-btn" onclick="this.closest('.modal').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div style="padding:2rem;">
                    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:1.5rem;margin-bottom:1.5rem;">
                        ${this._loanDetailField('Employee',          `${escapeHtml(loan.employee_name)}<br><small>${escapeHtml(loan.department)}</small>`)}
                        ${this._loanDetailField('Status',            `<span class="badge ${loan.status==='active'||loan.status==='approved'?'success':loan.status==='pending'?'warning':'danger'}">${escapeHtml(loan.status_display)}</span>`)}
                        ${this._loanDetailField('Loan Amount',       `$${escapeHtml(String(loan.loan_amount))}`)}
                        ${this._loanDetailField('Total Amount',      `$${escapeHtml(String(loan.total_amount))}`)}
                        ${this._loanDetailField('Remaining Balance', `<span style="color:var(--warning-color)">$${escapeHtml(String(loan.remaining_balance))}</span>`)}
                        ${this._loanDetailField('Amount Repaid',     `<span style="color:var(--success-color)">$${escapeHtml(String(loan.amount_repaid))}</span>`)}
                        ${this._loanDetailField('Monthly Payment',   `$${escapeHtml(String(loan.monthly_payment))}`)}
                        ${this._loanDetailField('Installments',      `${loan.installments_paid}/${loan.number_of_installments} (${loan.installments_remaining} remaining)`)}
                        ${this._loanDetailField('Start Date',        escapeHtml(loan.start_date))}
                        ${this._loanDetailField('End Date',          escapeHtml(loan.end_date))}
                    </div>
                    ${loan.purpose ? `<div style="margin-top:1.5rem;"><label style="font-weight:600;color:var(--text-light);font-size:.9rem;">Purpose</label><div style="margin-top:.5rem;padding:1rem;background:var(--bg-light);border-radius:8px;">${escapeHtml(loan.purpose)}</div></div>` : ''}
                    <div style="margin-top:1.5rem;">
                        <label style="font-weight:600;color:var(--text-light);font-size:.9rem;">Repayment Progress</label>
                        <div class="progress-bar" style="margin-top:.5rem;">
                            <div class="progress-fill" style="--progress:${loan.progress_percentage}%"></div>
                        </div>
                        <div style="text-align:center;margin-top:.5rem;font-weight:600;">${loan.progress_percentage}%</div>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(modal);
        modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
    }

    _loanDetailField(label, valueHtml) {
        return `<div>
            <label style="font-weight:600;color:var(--text-light);font-size:.9rem;">${label}</label>
            <div style="font-size:1.1rem;margin-top:.5rem;">${valueHtml}</div>
        </div>`;
    }

    showRepaymentHistoryModal(data) {
        const rows = data.repayments.length
            ? data.repayments.map(r => `
                <tr>
                    <td>${escapeHtml(r.payment_date)}</td>
                    <td>$${escapeHtml(String(r.amount))}</td>
                    <td>${escapeHtml(r.payment_method)}</td>
                    <td>${escapeHtml(r.created_by)}</td>
                    <td>${escapeHtml(r.notes || '-')}</td>
                </tr>`).join('')
            : '<tr><td colspan="5" style="text-align:center;padding:2rem;color:var(--text-light);">No repayments recorded yet.</td></tr>';

        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'flex';
        modal.innerHTML = `
            <div class="modal-content" style="max-width:900px;">
                <div class="modal-header">
                    <h2 class="modal-title">Repayment History</h2>
                    <button class="close-btn" onclick="this.closest('.modal').remove()"><i class="fas fa-times"></i></button>
                </div>
                <div style="padding:2rem;">
                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;margin-bottom:1.5rem;">
                        <div style="padding:1rem;background:var(--bg-light);border-radius:8px;">
                            <label style="font-weight:600;color:var(--text-light);font-size:.9rem;">Total Amount</label>
                            <div style="font-size:1.2rem;font-weight:700;margin-top:.5rem;">$${data.total_amount}</div>
                        </div>
                        <div style="padding:1rem;background:var(--bg-light);border-radius:8px;">
                            <label style="font-weight:600;color:var(--text-light);font-size:.9rem;">Total Repaid</label>
                            <div style="font-size:1.2rem;font-weight:700;color:var(--success-color);margin-top:.5rem;">$${data.total_repaid}</div>
                        </div>
                        <div style="padding:1rem;background:var(--bg-light);border-radius:8px;">
                            <label style="font-weight:600;color:var(--text-light);font-size:.9rem;">Remaining</label>
                            <div style="font-size:1.2rem;font-weight:700;color:var(--warning-color);margin-top:.5rem;">$${data.remaining_balance}</div>
                        </div>
                    </div>
                    <div class="table-container">
                        <table class="table">
                            <thead><tr><th>Date</th><th>Amount</th><th>Method</th><th>Recorded By</th><th>Notes</th></tr></thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(modal);
        modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
    }

    // ── Searchable employee select ────────────────
    bindSearchableEmployeeSelect() {
        const searchInput    = document.getElementById('employeeSearchInput');
        const dropdown       = document.getElementById('employeeDropdown');
        const hiddenInput    = document.getElementById('employee');
        if (!searchInput || !dropdown || !hiddenInput) return;

        const options = Array.from(dropdown.querySelectorAll('.dropdown-option'));

        searchInput.addEventListener('focus', () => {
            dropdown.style.display = 'block';
            this._filterEmployeeOptions(options, '');
        });
        searchInput.addEventListener('input', e =>
            this._filterEmployeeOptions(options, e.target.value.toLowerCase().trim())
        );
        options.forEach(opt => {
            opt.addEventListener('click', () => {
                hiddenInput.value   = opt.getAttribute('data-value');
                searchInput.value   = opt.getAttribute('data-text');
                dropdown.style.display = 'none';
            });
        });
        document.addEventListener('click', e => {
            const wrapper = searchInput.closest('.searchable-select-wrapper');
            if (wrapper && !wrapper.contains(e.target)) dropdown.style.display = 'none';
        });
    }

    _filterEmployeeOptions(options, term) {
        options.forEach(opt => {
            opt.style.display = !term || opt.textContent.toLowerCase().includes(term) ? '' : 'none';
        });
    }

    // ── Monthly payment calculator ────────────────
    bindPaymentCalculator() {
        const amtInput = document.getElementById('loan_amount');
        const instInput = document.getElementById('installments');
        const calc = () => {
            const preview = document.getElementById('monthlyPaymentPreview');
            if (!preview) return;
            const amt  = parseFloat(amtInput?.value) || 0;
            const inst = parseInt(instInput?.value)  || 1;
            preview.textContent = inst > 0 ? `$${(amt / inst).toFixed(2)}/month` : '--';
        };
        amtInput?.addEventListener('input', calc);
        instInput?.addEventListener('input', calc);
    }
}
