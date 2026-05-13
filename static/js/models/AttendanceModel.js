/**
 * AttendanceModel.js — Data access layer for Attendance (MVC Model)
 */

import { BaseModel } from '../core/BaseModel.js';

export class AttendanceModel extends BaseModel {
    constructor() {
        super('/attendance');
    }

    /**
     * Fetch a single attendance record as JSON (for editing).
     * @param {string|number} id
     */
    async getById(id) {
        return this.get(`/json/${id}/`);
    }

    /**
     * Fetch filtered attendance records via AJAX.
     * @param {URLSearchParams} params
     */
    async filter(params) {
        return this.get('/filter-ajax/', params);
    }

    /**
     * Mark new attendance.
     * @param {FormData} formData
     */
    async mark(formData) {
        return this.post('/mark/', formData);
    }

    /**
     * Update an existing attendance record.
     * @param {string|number} id
     * @param {FormData} formData
     */
    async update(id, formData) {
        return this.post(`/update/${id}/`, formData);
    }

    /**
     * Delete an attendance record.
     * @param {string|number} id
     */
    async delete(id) {
        return this.post(`/delete/${id}/`, new FormData());
    }
}
