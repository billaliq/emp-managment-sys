/**
 * LoanController.js — Orchestrates LoanModel + LoanView (MVC Controller)
 */

import { BaseController } from '../core/BaseController.js';
import { LoanModel }      from '../models/LoanModel.js';
import { LoanView }       from '../views/LoanView.js';

export class LoanController extends BaseController {
    constructor() {
        super(new LoanModel(), new LoanView());
    }

    init() {
        const v = this.view;

        // ── Tab switching ──────────────────────────
        v.tabs.forEach(tab => {
            tab.addEventListener('click', () => v.activateTab(tab.getAttribute('data-tab')));
        });

        // ── Modal open buttons ─────────────────────
        ['newLoanBtn','newLoanBtn2','newLoanBtn3'].forEach(id => {
            document.getElementById(id)?.addEventListener('click', () => v.openLoanModal());
        });
        ['addRepaymentBtn','addRepaymentBtn2'].forEach(id => {
            document.getElementById(id)?.addEventListener('click', () => v.openRepaymentModal());
        });
        document.getElementById('managePoolBtn')?.addEventListener('click', () => v.openPoolModal());

        // ── Modal close buttons ────────────────────
        document.getElementById('closeLoanModal')?.addEventListener('click',      () => v.closeLoanModal());
        document.getElementById('cancelLoanBtn')?.addEventListener('click',       () => v.closeLoanModal());
        document.getElementById('closeRepaymentModal')?.addEventListener('click', () => v.closeRepaymentModal());
        document.getElementById('cancelRepaymentBtn')?.addEventListener('click',  () => v.closeRepaymentModal());
        document.getElementById('closePoolModal')?.addEventListener('click',      () => v.closePoolModal());
        document.getElementById('cancelPoolBtn')?.addEventListener('click',       () => v.closePoolModal());

        // Backdrop clicks
        window.addEventListener('click', e => {
            if (e.target === v.loanModal)      v.closeLoanModal();
            if (e.target === v.repaymentModal) v.closeRepaymentModal();
            if (e.target === v.poolModal)      v.closePoolModal();
        });

        // ── Form submissions ───────────────────────
        v.loanForm?.addEventListener('submit',      e => { e.preventDefault(); this._handleLoanSubmit(); });
        v.repaymentForm?.addEventListener('submit', e => { e.preventDefault(); this._handleRepaymentSubmit(); });
        v.poolForm?.addEventListener('submit',      e => { e.preventDefault(); this._handlePoolSubmit(); });

        // ── Loan action buttons ────────────────────
        document.querySelectorAll('.view-loan').forEach(btn =>
            btn.addEventListener('click', () => this._handleViewLoan(btn.getAttribute('data-loan-id')))
        );
        document.querySelectorAll('.view-repayments').forEach(btn =>
            btn.addEventListener('click', () => this._handleViewRepayments(btn.getAttribute('data-loan-id')))
        );
        document.querySelectorAll('.approve-loan').forEach(btn =>
            btn.addEventListener('click', () => this._handleApproveLoan(btn.getAttribute('data-loan-id')))
        );
        document.querySelectorAll('.reject-loan').forEach(btn =>
            btn.addEventListener('click', () => this._handleRejectLoan(btn.getAttribute('data-loan-id')))
        );

        // ── UI helpers ────────────────────────────
        v.bindSearchableEmployeeSelect();
        v.bindPaymentCalculator();
    }

    // ── Private handlers ──────────────────────────

    async _handleLoanSubmit() {
        const v   = this.view;
        const btn = v.loanForm?.querySelector('button[type="submit"]');
        v.setButtonLoading(btn, true, 'Processing...');
        try {
            const fd   = new FormData(v.loanForm);
            const data = await this.model.create(fd);
            v.showNotification(data.message || 'Loan application submitted!', 'success');
            v.closeLoanModal();
            v.loanForm.reset();
            setTimeout(() => window.location.reload(), 1500);
        } catch (err) {
            this.handleError(err, 'Submitting loan');
            v.setButtonLoading(btn, false);
            if (btn) btn.innerHTML = btn._originalHtml || 'Submit Application';
        }
    }

    async _handleRepaymentSubmit() {
        const v   = this.view;
        const btn = v.repaymentForm?.querySelector('button[type="submit"]');
        v.setButtonLoading(btn, true, 'Recording...');
        try {
            const fd   = new FormData(v.repaymentForm);
            const data = await this.model.addRepayment(fd);
            v.showNotification(data.message || 'Repayment recorded!', 'success');
            v.closeRepaymentModal();
            v.repaymentForm.reset();
            setTimeout(() => window.location.reload(), 1500);
        } catch (err) {
            this.handleError(err, 'Recording repayment');
            v.setButtonLoading(btn, false);
        }
    }

    async _handlePoolSubmit() {
        const v   = this.view;
        const btn = v.poolForm?.querySelector('button[type="submit"]');
        v.setButtonLoading(btn, true, 'Updating...');
        try {
            const fd   = new FormData(v.poolForm);
            await this.model.updatePool(fd);
            v.showNotification('Loan pool updated!', 'success');
            v.closePoolModal();
            v.poolForm.reset();
        } catch (err) {
            this.handleError(err, 'Updating loan pool');
        } finally {
            v.setButtonLoading(btn, false);
        }
    }

    async _handleViewLoan(loanId) {
        try {
            const data = await this.model.getById(loanId);
            this.view.showLoanDetailsModal(data.loan);
        } catch (err) {
            this.handleError(err, 'Loading loan details');
        }
    }

    async _handleViewRepayments(loanId) {
        try {
            const data = await this.model.getRepayments(loanId);
            this.view.showRepaymentHistoryModal(data);
        } catch (err) {
            this.handleError(err, 'Loading repayment history');
        }
    }

    async _handleApproveLoan(loanId) {
        if (!confirm('Are you sure you want to approve this loan?')) return;
        try {
            const data = await this.model.updateStatus(loanId, 'approve');
            this.view.showNotification(data.message || 'Loan approved!', 'success');
            setTimeout(() => window.location.reload(), 1500);
        } catch (err) {
            this.handleError(err, 'Approving loan');
        }
    }

    async _handleRejectLoan(loanId) {
        if (!confirm('Are you sure you want to reject this loan?')) return;
        try {
            const data = await this.model.updateStatus(loanId, 'reject');
            this.view.showNotification(data.message || 'Loan rejected!', 'success');
            setTimeout(() => window.location.reload(), 1500);
        } catch (err) {
            this.handleError(err, 'Rejecting loan');
        }
    }
}
