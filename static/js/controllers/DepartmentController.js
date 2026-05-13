/**
 * DepartmentController.js — Orchestrates DepartmentModel + DepartmentView (MVC Controller)
 */

import { BaseController } from '../core/BaseController.js';
import { DepartmentModel } from '../models/DepartmentModel.js';
import { DepartmentView }  from '../views/DepartmentView.js';
import EventBus, { Events } from '../core/EventBus.js';

export class DepartmentController extends BaseController {
    constructor() {
        super(new DepartmentModel(), new DepartmentView());
        this._editMode      = false;
        this._editingDeptId = null;
    }

    init() {
        const v = this.view;

        // Bind office timing toggle
        v.bindOfficeTimingsToggle();

        // Open modal buttons
        const openAdd = () => { this._editMode = false; this._editingDeptId = null; v.openAddModal(); };
        document.getElementById('newDepartmentBtn')?.addEventListener('click', openAdd);

        // Delegate empty-state button (re-rendered dynamically)
        document.addEventListener('click', e => {
            if (e.target.closest('#newDepartmentBtnEmpty')) openAdd();
        });

        // Close main modal
        document.getElementById('closeModal')?.addEventListener('click', () => v.closeMainModal());
        document.getElementById('cancelBtn')?.addEventListener('click',  () => v.closeMainModal());
        v.bindBackdropClose(v.modal, () => v.closeMainModal());

        // Form submit
        v.form?.addEventListener('submit', e => { e.preventDefault(); this._handleFormSubmit(); });

        // Department grid — event delegation for edit / delete / assign / view
        v.grid?.addEventListener('click', e => {
            const card   = e.target.closest('.department-card');
            if (!card) return;
            const deptId = card.getAttribute('data-id');

            if (e.target.closest('.edit-btn'))             { e.preventDefault(); this._handleEdit(deptId, card); }
            if (e.target.closest('.delete-btn'))           { e.preventDefault(); this._handleDelete(deptId, card); }
            if (e.target.closest('.assign-employees-btn')) { e.preventDefault(); this._handleOpenAssign(deptId, card); }
            if (e.target.closest('.view-employees-btn'))   { e.preventDefault(); this._handleOpenView(deptId, card); }
        });

        // Assign modal close
        document.getElementById('closeAssignModal')?.addEventListener('click',  () => v.closeAssignModal());
        document.getElementById('cancelAssignBtn')?.addEventListener('click',   () => v.closeAssignModal());
        v.bindBackdropClose(v.assignModal, () => v.closeAssignModal());

        // Assign employee search
        v.employeeSearch?.addEventListener('input', e => v.filterAssignList(e.target.value));

        // Assign form submit
        v.assignForm?.addEventListener('submit', e => { e.preventDefault(); this._handleAssignSubmit(); });

        // View employees modal close
        document.getElementById('closeViewEmployeesModal')?.addEventListener('click', () => v.closeViewModal());
        document.getElementById('closeViewEmployeesBtn')?.addEventListener('click',   () => v.closeViewModal());
        v.bindBackdropClose(v.viewModal, () => v.closeViewModal());
    }

    // ── Private handlers ──────────────────────────

    async _handleFormSubmit() {
        const v  = this.view;
        const fd = new FormData(v.form);
        this.view.setButtonLoading(v.submitBtn, true, this._editMode ? 'Updating...' : 'Saving...');

        try {
            let data;
            if (this._editMode && this._editingDeptId) {
                data = await this.model.update(this._editingDeptId, fd);
                v.updateCard(data.department);
                v.showNotification('Department updated successfully!', 'success');
                v.updateStats();
                EventBus.emit(Events.DEPT_UPDATED, { department: data.department });
            } else {
                data = await this.model.create(fd);
                v.showNotification('Department created successfully!', 'success');
                setTimeout(() => window.location.reload(), 1000);
            }
            v.closeMainModal();
        } catch (err) {
            this.handleError(err, 'Saving department');
        } finally {
            this.view.setButtonLoading(v.submitBtn, false);
            v.submitBtn.innerHTML = this._editMode ? 'Update Department' : 'Save Department';
        }
    }

    async _handleEdit(deptId, card) {
        this._editMode      = true;
        this._editingDeptId = deptId;
        try {
            const data = await this.model.getById(deptId);
            // Merge basic card data with fetched detail
            const dept = {
                id:          deptId,
                name:        card.querySelector('.department-title')?.textContent,
                description: card.querySelector('.department-description')?.textContent,
                status:      card.querySelector('.department-status')?.textContent.trim().toLowerCase(),
                ...data,
            };
            this.view.openEditModal(dept);
        } catch (err) {
            this.handleError(err, 'Loading department details');
        }
    }

    async _handleDelete(deptId, card) {
        const name = card.querySelector('.department-title')?.textContent;
        if (!confirm(`Are you sure you want to delete "${name}"? This cannot be undone.`)) return;
        try {
            const data = await this.model.delete(deptId);
            this.view.showNotification(data.message || 'Department deleted!', 'success');
            this.view.removeCard(deptId);
            this.view.updateStats();
            EventBus.emit(Events.DEPT_DELETED, { id: deptId });
            setTimeout(() => window.location.reload(), 1000);
        } catch (err) {
            this.handleError(err, 'Deleting department');
        }
    }

    async _handleOpenAssign(deptId, card) {
        const deptName = card.querySelector('.department-title')?.textContent;
        this.view.openAssignModal(deptId, deptName);
        try {
            const data = await this.model.getEmployees(deptId);
            this.view.renderAssignList(data.all || [], data.assigned || []);
        } catch (err) {
            this.handleError(err, 'Loading employees');
            if (this.view.employeesList) this.view.employeesList.innerHTML = '<p class="error">Error loading employees.</p>';
        }
    }

    async _handleAssignSubmit() {
        const v       = this.view;
        const deptId  = v.assignDeptId?.value;
        const fd      = new FormData(v.assignForm);
        const btn     = document.getElementById('assignSubmitBtn');
        this.view.setButtonLoading(btn, true, 'Assigning...');
        try {
            const data = await this.model.assignEmployees(deptId, fd);
            v.showNotification(data.message || 'Employees assigned!', 'success');
            v.closeAssignModal();
            setTimeout(() => window.location.reload(), 1000);
        } catch (err) {
            this.handleError(err, 'Assigning employees');
        } finally {
            this.view.setButtonLoading(btn, false);
            if (btn) btn.innerHTML = 'Assign Selected Employees';
        }
    }

    async _handleOpenView(deptId, card) {
        const deptName = card.querySelector('.department-title')?.textContent;
        this.view.openViewModal(deptName);
        try {
            const data = await this.model.getEmployees(deptId);
            this.view.renderViewList(data.assigned || [], deptName);
        } catch (err) {
            this.handleError(err, 'Loading employees');
        }
    }
}
