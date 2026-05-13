/**
 * SettingsController.js — Orchestrates SettingsModel + SettingsView (MVC Controller)
 */

import { BaseController } from '../core/BaseController.js';
import { SettingsModel }  from '../models/SettingsModel.js';
import { SettingsView }   from '../views/SettingsView.js';

export class SettingsController extends BaseController {
    constructor() {
        super(new SettingsModel(), new SettingsView());
    }

    init() {
        const v = this.view;

        // Tab switching
        v.bindTabSwitching();

        // All settings forms
        document.querySelectorAll('.settings-form').forEach(form => {
            form.addEventListener('submit', e => {
                e.preventDefault();
                this._handleSave(form);
            });
        });
    }

    async _handleSave(form) {
        const v  = this.view;
        v.setSaveLoading(form, true);
        try {
            const fd   = new FormData(form);
            const data = await this.model.save(fd);
            v.showNotification(data.message || 'Settings saved successfully!', 'success');
        } catch (err) {
            this.handleError(err, 'Saving settings');
        } finally {
            v.setSaveLoading(form, false);
        }
    }
}
