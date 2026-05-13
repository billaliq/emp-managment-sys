/**
 * EmployeeController.js — Orchestrates EmployeeModel + EmployeeView (MVC Controller)
 */

import { BaseController } from '../core/BaseController.js';
import { EmployeeModel }  from '../models/EmployeeModel.js';
import { EmployeeView }   from '../views/EmployeeView.js';

const DOC_SLOTS = [
    { input: '#cnicUpload',     name: 'CNIC Copy' },
    { input: '#passportUpload', name: 'Passport Size Photo' },
    { input: '#resumeUpload',   name: 'Updated Resume' },
    { input: '#eduUpload',      name: 'Educational Certificate' },
    { input: '#expUpload',      name: 'Experience Letter' },
    { input: '#offerUpload',    name: 'Signed Offer Letter' },
    { input: '#ndaUpload',      name: 'Signed NDA Form' },
];

export class EmployeeController extends BaseController {
    constructor() {
        super(new EmployeeModel(), new EmployeeView());
    }

    init() {
        const v = this.view;

        // Sync hidden employee code → visible display field
        const codeHidden  = v.form?.querySelector('input[name="code"]');
        const codeDisplay = document.getElementById('employeeCodeDisplay');
        if (codeHidden && codeDisplay && codeHidden.value && !codeDisplay.value) {
            codeDisplay.value = codeHidden.value;
        }

        // Tab navigation
        v.bindTabClicks(tabId => v.activateTab(tabId));

        v.bindNextButtons((nextTabId, currentTabContent) => {
            if (!v.validateTabFields(currentTabContent)) {
                v.showNotification('Please fill all required fields before continuing.', 'warning');
                return;
            }
            v.activateTab(nextTabId.replace('Tab', ''));
        });

        v.bindPrevButtons(prevTabId => v.activateTab(prevTabId.replace('Tab', '')));

        // Photo & document uploads
        v.bindPhotoUpload();
        v.bindDocumentUploads(DOC_SLOTS);
        v.bindAddAdditionalDocument();

        // Form submission
        if (v.form) {
            v.form.addEventListener('submit', e => this._handleSubmit(e));
        }

        // Cancel button
        v.cancelBtn?.addEventListener('click', () => {
            if (confirm('Are you sure you want to cancel? All unsaved changes will be lost.')) {
                v.resetForm();
            }
        });

        // Submit button click fallback
        document.querySelectorAll('.save-employee-btn').forEach(btn => {
            btn.addEventListener('click', function (e) {
                if (this.disabled) { e.preventDefault(); return false; }
            });
        });
    }

    _handleSubmit(e) {
        const v            = this.view;
        const employeeIdEl = v.form.querySelector('input[name="employee_id"]');
        const isUpdate     = employeeIdEl?.value?.trim();

        if (!isUpdate) {
            const codeField   = v.form.querySelector('input[name="code"]');
            const codeDisplay = document.getElementById('employeeCodeDisplay');
            const code        = codeField?.value?.trim() || codeDisplay?.value?.trim();
            if (!code) {
                e.preventDefault();
                v.showNotification('No employee ID assigned. Please ensure the employee ID is available.', 'error');
                return;
            }
        }

        // Re-enable disabled fields so their values are submitted
        v.reenableDisabledFields();
        v.setSubmitLoading(true);
        // Allow native form POST to Django backend
    }
}
