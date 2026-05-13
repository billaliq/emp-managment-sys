/**
 * PayrollView.js — DOM rendering layer for Payroll (MVC View)
 */

import { BaseView } from '../core/BaseView.js';

export class PayrollView extends BaseView {
    constructor() {
        super();
        this.generateModal = document.getElementById('generatePayrollModal');
        this.generateForm  = document.getElementById('generatePayrollForm');
    }

    openGenerateModal()  { this.openModal(this.generateModal); }
    closeGenerateModal() { this.closeModal(this.generateModal); }

    setGenerateLoading(isLoading) {
        const btn = this.generateForm?.querySelector('button[type="submit"]');
        this.setButtonLoading(btn, isLoading, 'Generating...');
    }
}
