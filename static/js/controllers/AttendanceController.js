/**
 * AttendanceController.js — Orchestrates AttendanceModel + AttendanceView (MVC Controller)
 */

import { BaseController }   from '../core/BaseController.js';
import { AttendanceModel }  from '../models/AttendanceModel.js';
import { AttendanceView }   from '../views/AttendanceView.js';
import { debounce }         from '../core/Utils.js';

export class AttendanceController extends BaseController {
    constructor() {
        super(new AttendanceModel(), new AttendanceView());
    }

    init() {
        const v = this.view;

        // Set today as default in date filters & form date
        v.setDateFiltersToToday();

        // ── Mark attendance modal ──────────────────
        document.getElementById('markAttendanceBtn')?.addEventListener('click', () => {
            const attId = document.getElementById('attendanceId');
            if (attId) attId.value = '';
            if (v.form) v.form.action = '/attendance/mark/';
            v.openModal();
        });
        document.getElementById('closeMarkAttendanceModal')?.addEventListener('click', () => v.closeModal());
        document.getElementById('cancelMarkAttendance')?.addEventListener('click',   () => v.closeModal());
        v.bindBackdropClose(v.modal, () => v.closeModal());

        // Show / hide leave type field
        v.formStatus?.addEventListener('change', () =>
            v.setLeaveTypeVisible(v.formStatus.value === 'leave')
        );
        v.setLeaveTypeVisible(v.formStatus?.value === 'leave');

        // ── Filter panel toggle / clear ────────────
        v.toggleFiltersBtn?.addEventListener('click', () => v.toggleFilters());
        document.getElementById('clearFiltersBtn')?.addEventListener('click', () => {
            v.clearFilterInputs();
            const url = new URL(window.location);
            url.search = '';
            window.location.href = url.toString();
        });

        // ── Quick filter buttons ───────────────────
        document.querySelectorAll('.btn-filter').forEach(btn => {
            btn.addEventListener('click', () => {
                const status = btn.dataset.status;
                v.syncQuickFilterUI(status);
                const p = v.collectFilterParams();
                if (status && status !== 'all') p.set('status', status);
                p.set('page', '1');
                this._fetchFiltered(p);
            });
        });

        // ── Advanced filter form ───────────────────
        v.filterForm?.addEventListener('submit', e => { e.preventDefault(); this._fetchFiltered(); });

        // Auto-apply on input change
        const autoFilter = debounce(() => this._fetchFiltered(), 500);
        v.employeeFilter?.addEventListener('input', autoFilter);
        v.dateFromFilter?.addEventListener('change', () => this._fetchFiltered());
        v.dateToFilter?.addEventListener('change',   () => this._fetchFiltered());
        v.statusFilter?.addEventListener('change',   () => this._fetchFiltered());
        v.teamFilter?.addEventListener('change',     () => this._fetchFiltered());
        v.statusFilterTeam?.addEventListener('change', () => this._fetchFiltered());

        // Per-page selector
        document.getElementById('perPageSelect')?.addEventListener('change', () => this._fetchFiltered());

        // ── Pagination via EventBus ────────────────
        document.addEventListener('attendance:goToPage', e => this._goToPage(e.detail));

        // ── Edit attendance buttons (initial) ──────
        this._bindEditButtons();
    }

    // ── Private helpers ───────────────────────────

    _bindEditButtons() {
        document.querySelectorAll('.edit-attendance').forEach(btn => {
            btn.addEventListener('click', () => this._handleEdit(btn.dataset.id));
        });
    }

    async _handleEdit(id) {
        try {
            const data = await this.model.getById(id);
            this.view.populateEditForm(data);
        } catch (err) {
            this.handleError(err, 'Loading attendance record');
        }
    }

    async _fetchFiltered(params = null) {
        const v = this.view;
        v.showTableLoading();

        let p = params;
        if (!p) {
            p = v.collectFilterParams();
            p.set('page', '1');
        }

        // Ensure per_page is always set
        if (!p.has('per_page')) {
            const sel = document.getElementById('perPageSelect');
            p.set('per_page', sel?.value || '50');
        }

        try {
            const data = await this.model.filter(p);
            v.renderRows(data.records || [], data.pagination);
            v.showFilterCount(data.pagination?.total_count ?? (data.records?.length || 0));
            // Re-bind edit buttons on newly rendered rows
            this._bindEditButtons();
        } catch (err) {
            this.handleError(err, 'Fetching attendance records');
        }
    }

    _goToPage(page) {
        const p = this.view.collectFilterParams();
        p.set('page', String(page));
        this._fetchFiltered(p);
    }
}
