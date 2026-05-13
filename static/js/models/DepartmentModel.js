/**
 * DepartmentModel.js — Data access layer for Departments (MVC Model)
 * All Department API calls live here. Zero DOM knowledge.
 */

import { BaseModel } from '../core/BaseModel.js';

export class DepartmentModel extends BaseModel {
    constructor() {
        super('/departments');
    }

    /** Fetch all departments (page load data is already in DOM, this is for refresh) */
    async getAll() {
        return this.get('/');
    }

    /** Fetch a single department's full details (including head & office timings) */
    async getById(id) {
        return this.get(`/${id}/`);
    }

    /**
     * Create a new department.
     * @param {FormData} formData
     */
    async create(formData) {
        return this.post('/create/', formData);
    }

    /**
     * Update an existing department.
     * @param {string|number} id
     * @param {FormData} formData
     */
    async update(id, formData) {
        return this.post(`/update/${id}/`, formData);
    }

    /**
     * Delete a department.
     * @param {string|number} id
     */
    async delete(id) {
        const fd = new FormData();
        return this.post(`/delete/${id}/`, fd);
    }

    /**
     * Get employees for a department (both assigned and all available).
     * @param {string|number} id
     */
    async getEmployees(id) {
        return this.get(`/${id}/employees/`);
    }

    /**
     * Assign selected employees to a department.
     * @param {string|number} id
     * @param {FormData} formData  should contain employee_ids[]
     */
    async assignEmployees(id, formData) {
        return this.post(`/${id}/assign/`, formData);
    }
}
