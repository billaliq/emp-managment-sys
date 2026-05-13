/**
 * SettingsModel.js — Data access layer for Settings (MVC Model)
 */

import { BaseModel } from '../core/BaseModel.js';

export class SettingsModel extends BaseModel {
    constructor() {
        super('/settings');
    }

    /**
     * Save system settings.
     * @param {FormData} formData
     */
    async save(formData) {
        return this.post('/save/', formData);
    }

    /**
     * Update appearance / theme settings.
     * @param {FormData} formData
     */
    async saveAppearance(formData) {
        return this.post('/appearance/', formData);
    }
}
