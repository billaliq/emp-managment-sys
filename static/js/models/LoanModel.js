/**
 * LoanModel.js — Data access layer for Loans (MVC Model)
 */

import { BaseModel } from '../core/BaseModel.js';

export class LoanModel extends BaseModel {
    constructor() {
        super('/loans');
    }

    /**
     * Fetch full details of a single loan.
     * @param {string|number} id
     */
    async getById(id) {
        return this.get(`/${id}/details/`);
    }

    /**
     * Fetch repayment history for a loan.
     * @param {string|number} id
     */
    async getRepayments(id) {
        return this.get(`/${id}/repayments/`);
    }

    /**
     * Create a new loan application.
     * @param {FormData} formData
     */
    async create(formData) {
        // Interest rate is always 0 per business logic
        formData.set('interest_rate', '0');
        return this.post('/create/', formData);
    }

    /**
     * Add a repayment to a loan.
     * @param {FormData} formData
     */
    async addRepayment(formData) {
        return this.post('/add-repayment/', formData);
    }

    /**
     * Update loan status (approve / reject).
     * @param {string|number} loanId
     * @param {'approve'|'reject'} action
     */
    async updateStatus(loanId, action) {
        const fd = new FormData();
        fd.append('loan_id', loanId);
        fd.append('action', action);
        return this.post('/update-status/', fd);
    }

    /**
     * Update loan pool settings.
     * @param {FormData} formData
     */
    async updatePool(formData) {
        return this.post('/update-pool/', formData);
    }
}
