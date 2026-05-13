/**
 * DepartmentView.js — DOM rendering layer for Departments (MVC View)
 * Knows about the DOM only. No API calls.
 */

import { BaseView } from '../core/BaseView.js';
import { formatDate, escapeHtml, capitalize } from '../core/Utils.js';

export class DepartmentView extends BaseView {
    constructor() {
        super();
        // ── Main modal ──
        this.modal        = document.getElementById('newDepartmentModal');
        this.modalTitle   = document.getElementById('modalTitle');
        this.form         = document.getElementById('departmentForm');
        this.submitBtn    = document.getElementById('submitBtn');
        this.deptIdInput  = document.getElementById('deptId');

        // ── Grid ──
        this.grid = document.getElementById('departmentsGrid');

        // ── Office timing fields ──
        this.useCustomTimings    = document.getElementById('useCustomTimings');
        this.officeTimingsFields = document.getElementById('officeTimingsFields');
        this.officeStartTime     = document.getElementById('officeStartTime');
        this.officeEndTime       = document.getElementById('officeEndTime');
        this.gracePeriodMinutes  = document.getElementById('gracePeriodMinutes');

        // ── Assign employees modal ──
        this.assignModal       = document.getElementById('assignEmployeesModal');
        this.assignModalTitle  = document.getElementById('assignModalTitle');
        this.assignForm        = document.getElementById('assignEmployeesForm');
        this.assignDeptId      = document.getElementById('assignDeptId');
        this.employeesList     = document.getElementById('employeesList');
        this.employeeSearch    = document.getElementById('employeeSearchInput');

        // ── View employees modal ──
        this.viewModal        = document.getElementById('viewEmployeesModal');
        this.viewModalTitle   = document.getElementById('viewEmployeesModalTitle');
        this.viewContent      = document.getElementById('viewEmployeesContent');

        // Cached data for filtering
        this._allEmployees      = [];
        this._assignedEmployees = [];
    }

    // ─────────────────────────────────────────────
    // Main modal
    // ─────────────────────────────────────────────

    openAddModal() {
        if (this.modalTitle) this.modalTitle.textContent = 'Add Department';
        if (this.form)       this.form.reset();
        if (this.deptIdInput) this.deptIdInput.value = '';
        if (this.submitBtn)   this.submitBtn.textContent = 'Save Department';
        this._resetOfficeTimings();
        this.openModal(this.modal);
    }

    openEditModal(department) {
        if (this.modalTitle)  this.modalTitle.textContent = 'Edit Department';
        if (this.submitBtn)   this.submitBtn.textContent  = 'Update Department';
        if (this.deptIdInput) this.deptIdInput.value = department.id;

        // Fill basic fields
        const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
        set('deptName',        department.name);
        set('deptDescription', department.description);
        set('deptStatus',      department.status);
        set('deptHead',        department.head?.id || '');

        // Office timings
        if (this.useCustomTimings) {
            this.useCustomTimings.checked = !!department.use_custom_timings;
            this._toggleOfficeTimingsFields();
            if (department.use_custom_timings) {
                if (this.officeStartTime)    this.officeStartTime.value    = department.office_start_time || '';
                if (this.officeEndTime)      this.officeEndTime.value      = department.office_end_time   || '';
                if (this.gracePeriodMinutes) this.gracePeriodMinutes.value = department.grace_period_minutes || '';
            }
        }
        this.openModal(this.modal);
    }

    closeMainModal() {
        this.closeModal(this.modal);
        this._resetOfficeTimings();
    }

    _toggleOfficeTimingsFields() {
        if (this.useCustomTimings && this.officeTimingsFields) {
            this.setVisible(this.officeTimingsFields, this.useCustomTimings.checked);
        }
    }

    _resetOfficeTimings() {
        if (this.useCustomTimings) this.useCustomTimings.checked = false;
        this._toggleOfficeTimingsFields();
    }

    bindOfficeTimingsToggle() {
        if (this.useCustomTimings) {
            this.useCustomTimings.addEventListener('change', () => this._toggleOfficeTimingsFields());
        }
    }

    // ─────────────────────────────────────────────
    // Department cards
    // ─────────────────────────────────────────────

    /** Insert a brand-new card at the top of the grid */
    prependCard(department) {
        const emptyState = document.getElementById('emptyState');
        if (emptyState) emptyState.remove();

        const card = this._buildCardElement(department);
        this.grid?.prepend(card);
        requestAnimationFrame(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        });
    }

    /** Update an existing card in place */
    updateCard(department) {
        const card = this.grid?.querySelector(`.department-card[data-id="${department.id}"]`);
        if (!card) return;

        const q = (sel) => card.querySelector(sel);
        const title    = q('.department-title');
        const desc     = q('.department-description');
        const badge    = q('.department-status');
        const empCount = q('.employee-count');
        const headEl   = q('.department-details p:nth-child(2)');
        const updEl    = q('.department-details p:nth-child(4)');

        if (title)    title.textContent = department.name;
        if (desc)     desc.textContent  = department.description || 'No description provided';
        if (badge) {
            badge.textContent = capitalize(department.status);
            badge.className = `department-status badge ${department.status === 'active' ? 'success' : 'danger'}`;
        }
        if (empCount && department.employee_count !== undefined) {
            empCount.textContent = department.employee_count;
        }
        if (headEl) {
            const headName = this._resolveHeadName(department);
            headEl.innerHTML = `<strong>Department Head:</strong> ${escapeHtml(headName)}`;
        }
        if (updEl && department.updated_at) {
            updEl.innerHTML = `<strong>Last Updated:</strong> ${formatDate(department.updated_at)}`;
        }
    }

    /** Remove a card from the DOM */
    removeCard(id) {
        const card = this.grid?.querySelector(`.department-card[data-id="${id}"]`);
        if (card) {
            card.style.opacity = '0';
            card.style.transform = 'translateY(-10px)';
            card.style.transition = 'opacity 0.3s, transform 0.3s';
            setTimeout(() => card.remove(), 300);
        }
    }

    _buildCardElement(dept) {
        const card = document.createElement('div');
        card.className = 'department-card fade-in-up';
        card.setAttribute('data-id', dept.id);
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.3s, transform 0.3s';

        const headName = this._resolveHeadName(dept);
        card.innerHTML = `
            <div class="department-header">
                <div class="department-icon"><i class="fas fa-building"></i></div>
                <span class="department-status badge ${dept.status === 'active' ? 'success' : 'danger'}">
                    ${escapeHtml(capitalize(dept.status))}
                </span>
            </div>
            <h3 class="department-title">${escapeHtml(dept.name)}</h3>
            <p class="department-description">${escapeHtml(dept.description || 'No description provided')}</p>
            <div class="department-details">
                <p><strong>Employees:</strong> <span class="employee-count">0</span></p>
                <p><strong>Department Head:</strong> ${escapeHtml(headName)}</p>
                <p><strong>Date Added:</strong> ${formatDate(dept.created_at)}</p>
                <p><strong>Last Updated:</strong> ${formatDate(dept.updated_at)}</p>
            </div>
            <div class="department-actions">
                <button class="btn btn-success edit-btn" data-id="${dept.id}">
                    <i class="fas fa-edit"></i> Edit
                </button>
                <button class="btn btn-danger delete-btn" data-id="${dept.id}">
                    <i class="fas fa-trash"></i> Delete
                </button>
            </div>
        `;
        return card;
    }

    _resolveHeadName(dept) {
        if (dept.head) {
            if (typeof dept.head === 'string') return dept.head;
            if (dept.head.firstname) return `${dept.head.firstname} ${dept.head.lastname || ''}`.trim();
        }
        return dept.head_name || 'Not assigned';
    }

    // ─────────────────────────────────────────────
    // Stats
    // ─────────────────────────────────────────────

    updateStats() {
        const cards    = document.querySelectorAll('.department-card');
        let active = 0, inactive = 0;
        cards.forEach(c => {
            const badge = c.querySelector('.department-status');
            if (badge?.textContent.trim().toLowerCase() === 'active') active++;
            else inactive++;
        });
        const set = (sel, val) => { const el = document.querySelector(sel); if (el) el.textContent = val; };
        set('.stats-grid .stat-card:nth-child(1) .stat-info h3', cards.length);
        set('.stats-grid .stat-card:nth-child(2) .stat-info h3', active);
        set('.stats-grid .stat-card:nth-child(3) .stat-info h3', inactive);
    }

    // ─────────────────────────────────────────────
    // Assign employees modal
    // ─────────────────────────────────────────────

    openAssignModal(deptId, deptName) {
        if (this.assignModalTitle) this.assignModalTitle.textContent = `Assign Employees to ${deptName}`;
        if (this.assignDeptId)     this.assignDeptId.value = deptId;
        if (this.employeesList)    this.employeesList.innerHTML = '<p>Loading employees...</p>';
        if (this.employeeSearch)   this.employeeSearch.value = '';
        this._allEmployees = [];
        this._assignedEmployees = [];
        this.openModal(this.assignModal);
    }

    closeAssignModal() {
        this.closeModal(this.assignModal);
        if (this.employeesList) this.employeesList.innerHTML = '';
    }

    renderAssignList(allEmployees, assignedEmployees, search = '') {
        this._allEmployees      = allEmployees;
        this._assignedEmployees = assignedEmployees;

        const assignedIds = assignedEmployees.map(e => e.id);
        let filtered = allEmployees;

        if (search.trim()) {
            const term = search.toLowerCase().trim();
            filtered = allEmployees.filter(e => {
                const name = `${e.firstname || ''} ${e.lastname || ''}`.toLowerCase();
                return (e.code || '').toLowerCase().includes(term) || name.includes(term);
            });
        }

        if (!filtered.length) {
            this.employeesList.innerHTML = '<p>No employees found.</p>';
            return;
        }

        this.employeesList.innerHTML = filtered.map(emp => {
            const isAssigned = assignedIds.includes(emp.id);
            return `
                <label style="display:flex;align-items:center;padding:0.5rem;margin-bottom:0.5rem;
                              cursor:pointer;border-radius:4px;background:${isAssigned ? '#e8f5e9' : '#f5f5f5'};">
                    <input type="checkbox" name="employee_ids[]" value="${emp.id}"
                           ${isAssigned ? 'checked' : ''} style="margin-right:0.5rem;">
                    <span>${escapeHtml(emp.code)} - ${escapeHtml(emp.firstname)} ${escapeHtml(emp.lastname || '')}</span>
                    ${isAssigned ? '<span style="margin-left:auto;color:green;font-size:0.85rem;">(Already assigned)</span>' : ''}
                </label>
            `;
        }).join('');
    }

    filterAssignList(search) {
        this.renderAssignList(this._allEmployees, this._assignedEmployees, search);
    }

    // ─────────────────────────────────────────────
    // View employees modal
    // ─────────────────────────────────────────────

    openViewModal(deptName) {
        if (this.viewModalTitle) this.viewModalTitle.textContent = `Employees in ${deptName}`;
        if (this.viewContent)    this.viewContent.innerHTML = `
            <div style="text-align:center;padding:2rem;">
                <i class="fas fa-spinner fa-spin" style="font-size:2rem;color:#667eea;"></i>
                <p style="margin-top:1rem;color:#666;">Loading employees...</p>
            </div>`;
        this.openModal(this.viewModal);
    }

    closeViewModal() { this.closeModal(this.viewModal); }

    renderViewList(employees, deptName) {
        if (!employees.length) {
            this.viewContent.innerHTML = `
                <div style="text-align:center;padding:2rem;">
                    <i class="fas fa-users" style="font-size:3rem;color:#cbd5e0;margin-bottom:1rem;"></i>
                    <h3>No Employees</h3>
                    <p>This department has no employees assigned yet.</p>
                </div>`;
            return;
        }

        const rows = employees.map(emp => {
            const name       = `${emp.firstname || ''} ${emp.lastname || ''}`.trim() || 'N/A';
            const email      = emp.official_email || emp.email || 'N/A';
            const position   = emp.position__name || 'Not assigned';
            const isActive   = emp.status === 1;
            const statusColor = isActive ? '#48bb78' : '#cbd5e0';
            const dateHired  = formatDate(emp.date_hired);
            const initial    = (emp.firstname || 'E')[0].toUpperCase();

            return `
                <div style="padding:1rem;margin-bottom:0.75rem;background:white;border-radius:8px;
                            border:1px solid #e0e0e0;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
                    <div style="display:flex;align-items:center;gap:1rem;">
                        <div style="width:48px;height:48px;border-radius:50%;flex-shrink:0;
                                    background:linear-gradient(135deg,#667eea,#764ba2);
                                    display:flex;align-items:center;justify-content:center;
                                    color:white;font-weight:bold;font-size:1.2rem;">
                            ${initial}
                        </div>
                        <div style="flex:1;min-width:0;">
                            <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.25rem;">
                                <h4 style="margin:0;">${escapeHtml(name)}</h4>
                                <span style="padding:0.125rem 0.5rem;border-radius:12px;font-size:0.75rem;
                                             background:${statusColor}20;color:${statusColor};">
                                    ${isActive ? 'Active' : 'Inactive'}
                                </span>
                            </div>
                            <div style="display:flex;flex-wrap:wrap;gap:1rem;font-size:0.875rem;color:#666;">
                                <span><i class="fas fa-id-badge" style="color:#667eea;"></i> <strong>ID:</strong> ${escapeHtml(emp.code || 'N/A')}</span>
                                <span><i class="fas fa-briefcase" style="color:#667eea;"></i> <strong>Position:</strong> ${escapeHtml(position)}</span>
                                <span><i class="fas fa-envelope" style="color:#667eea;"></i> <strong>Email:</strong> ${escapeHtml(email)}</span>
                                <span><i class="fas fa-calendar-alt" style="color:#667eea;"></i> <strong>Hired:</strong> ${dateHired}</span>
                            </div>
                        </div>
                    </div>
                </div>`;
        }).join('');

        this.viewContent.innerHTML = `
            <p style="color:#666;font-size:0.875rem;margin-bottom:1rem;">
                <strong>Total Employees:</strong> ${employees.length}
            </p>
            <div style="max-height:400px;overflow-y:auto;">${rows}</div>`;
    }

    // ─────────────────────────────────────────────
    // Empty state
    // ─────────────────────────────────────────────

    showEmptyState() {
        if (!this.grid) return;
        this.grid.innerHTML = `
            <div class="empty-state" id="emptyState">
                <i class="fas fa-building"></i>
                <h3>No Departments Found</h3>
                <p>Get started by creating your first department</p>
                <button id="newDepartmentBtnEmpty" class="btn btn-primary">
                    <i class="fas fa-plus"></i> Add Department
                </button>
            </div>`;
    }
}
