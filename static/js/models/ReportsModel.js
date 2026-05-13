/**
 * ReportsModel.js — Data access layer for Reports (MVC Model)
 */

import { BaseModel } from '../core/BaseModel.js';

export class ReportsModel extends BaseModel {
    constructor() {
        super('/reports');
    }

    /**
     * Fetch report data with filters.
     * @param {URLSearchParams} params
     */
    async fetch(params) {
        return this.get('/data/', params);
    }

    /**
     * Export a report to CSV/Excel.
     * @param {string} type  'attendance', 'payroll', etc.
     * @param {URLSearchParams} params
     */
    async export(type, params) {
        return this.get(`/export/${type}/`, params);
    }
}
