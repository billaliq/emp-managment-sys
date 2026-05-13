/**
 * EmployeeModel.js — Data access layer for Employees (MVC Model)
 */

import { BaseModel } from '../core/BaseModel.js';

export class EmployeeModel extends BaseModel {
    constructor() {
        super('/employees');
    }

    /** Fetch details for a single employee (used in team member detail view) */
    async getById(id) {
        return this.get(`/${id}/details/`);
    }

    /** Fetch all available employees (not yet in a specific team) */
    async getAvailable(teamId = null) {
        const params = teamId ? { team_id: teamId } : {};
        return this.get('/available/', params);
    }

    /**
     * Submit the employee creation/update form.
     * The form posts to Django normally via HTML form submit (not AJAX),
     * so this method is provided for any AJAX-only use cases.
     * @param {FormData} formData
     */
    async create(formData) {
        return this.post('/create/', formData);
    }

    /**
     * Update an existing employee.
     * @param {string|number} id
     * @param {FormData} formData
     */
    async update(id, formData) {
        return this.post(`/${id}/update/`, formData);
    }

    /**
     * Generate the next available employee code.
     */
    async generateCode() {
        return this.get('/generate-code/');
    }
}
