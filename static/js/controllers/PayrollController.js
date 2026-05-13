/**
 * PayrollController.js — Orchestrates PayrollModel + PayrollView (MVC Controller)
 */

import { BaseController } from '../core/BaseController.js';
import { PayrollModel }   from '../models/PayrollModel.js';
import { PayrollView }    from '../views/PayrollView.js';

export class PayrollController extends BaseController {
    constructor() {
        super(new PayrollModel(), new PayrollView());
    }

    init() {
        const v = this.view;

        // Open / close generate modal
        document.getElementById('generatePayrollBtn')?.addEventListener('click', () => v.openGenerateModal());
        document.getElementById('closeGenerateModal')?.addEventListener('click', () => v.closeGenerateModal());
        document.getElementById('cancelGenerateBtn')?.addEventListener('click',  () => v.closeGenerateModal());
        v.bindBackdropClose(v.generateModal, () => v.closeGenerateModal());

        // Form submit
        v.generateForm?.addEventListener('submit', e => {
            e.preventDefault();
            this._handleGenerate();
        });
    }

    async _handleGenerate() {
        const v  = this.view;
        v.setGenerateLoading(true);
        try {
            const fd   = new FormData(v.generateForm);
            const data = await this.model.generate(fd);
            v.showNotification(data.message || 'Payroll generated successfully!', 'success');
            v.closeGenerateModal();
            setTimeout(() => window.location.reload(), 1500);
        } catch (err) {
            this.handleError(err, 'Generating payroll');
        } finally {
            v.setGenerateLoading(false);
        }
    }
}
