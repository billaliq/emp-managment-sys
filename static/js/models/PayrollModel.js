/**
 * PayrollModel.js — Data access layer for Payroll (MVC Model)
 */

import { BaseModel } from '../core/BaseModel.js';

export class PayrollModel extends BaseModel {
    constructor() {
        super('/payroll');
    }

    /**
     * Generate payroll for a pay period.
     * @param {FormData} formData
     */
    async generate(formData) {
        return this.post('/generate/', formData);
    }

    /**
     * Fetch payroll record details.
     * @param {string|number} id
     */
    async getById(id) {
        return this.get(`/${id}/`);
    }

    /**
     * Approve a payroll record.
     * @param {string|number} id
     */
    async approve(id) {
        return this.post(`/${id}/approve/`, new FormData());
    }

    /**
     * Filter payroll records.
     * @param {URLSearchParams} params
     */
    async filter(params) {
        return this.get('/filter/', params);
    }
}
