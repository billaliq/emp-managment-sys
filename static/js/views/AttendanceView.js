/**
 * AttendanceView.js — DOM rendering layer for Attendance (MVC View)
 */

import { BaseView } from '../core/BaseView.js';
import { escapeHtml, todayISO } from '../core/Utils.js';

export class AttendanceView extends BaseView {
    constructor() {
        super();
        this.modal               = document.getElementById('markAttendanceModal');
        this.form                = document.getElementById('attendanceForm');
        this.formStatus          = document.getElementById('formStatus');
        this.leaveTypeGroup      = document.getElementById('leaveTypeGroup');
        this.filterSection       = document.getElementById('filterSection');
        this.toggleFiltersBtn    = document.getElementById('toggleFiltersBtn');
        this.filterForm          = document.getElementById('attendanceFilterForm');
        this.employeeFilter      = document.getElementById('employeeFilter');
        this.dateFromFilter      = document.getElementById('dateFromFilter');
        this.dateToFilter        = document.getElementById('dateToFilter');
        this.statusFilter        = document.getElementById('statusFilter');
        this.teamFilter          = document.getElementById('teamFilter');
        this.statusFilterTeam    = document.getElementById('statusFilterTeam');
        this.csrfToken           = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    // ── Modal ────────────────────────────────────
    openModal() { this.modal && this.modal.classList.add('active'); }

    closeModal() {
        if (!this.modal) return;
        this.modal.classList.remove('active');
        this.form?.reset();
        const attId = document.getElementById('attendanceId');
        if (attId) attId.value = '';
        if (this.form) this.form.action = '/attendance/mark/';
        this.setLeaveTypeVisible(false);
    }

    setLeaveTypeVisible(visible) {
        this.setVisible(this.leaveTypeGroup, visible);
        if (!visible) {
            const lt = document.getElementById('formLeaveType');
            if (lt) lt.value = '';
        }
    }

    populateEditForm(data) {
        const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val ?? ''; };
        set('attendanceId',   data.id);
        set('formEmployee',   data.employee_id);
        set('formDate',       data.date);
        set('formCheckIn',    data.check_in);
        set('formCheckOut',   data.check_out);
        set('formStatus',     data.status === 'leave' ? 'leave' : (data.status || 'present'));
        set('formOvertime',   data.overtime_hours);
        set('formNotes',      data.notes);
        if (data.status === 'leave' && data.leave_type) {
            set('formLeaveType', data.leave_type);
        }
        if (this.form) this.form.action = `/attendance/update/${data.id}/`;
        this.setLeaveTypeVisible(data.status === 'leave');
        this.openModal();
    }

    // ── Filters ──────────────────────────────────
    toggleFilters() {
        const visible = this.filterSection?.style.display === 'block';
        this.setVisible(this.filterSection, !visible);
        if (this.toggleFiltersBtn) {
            this.toggleFiltersBtn.innerHTML = visible
                ? '<i class="fas fa-filter"></i> Filters'
                : '<i class="fas fa-times"></i> Hide Filters';
            this.toggleFiltersBtn.classList.toggle('active', !visible);
        }
    }

    clearFilterInputs() {
        [this.employeeFilter, this.dateFromFilter, this.dateToFilter,
         this.statusFilter, this.teamFilter, this.statusFilterTeam].forEach(el => {
            if (el) el.value = '';
        });
        document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
        const allBtn = document.querySelector('.btn-filter[data-status="all"]');
        if (allBtn) allBtn.classList.add('active');
    }

    setDateFiltersToToday() {
        const today = todayISO();
        if (this.dateFromFilter && !this.dateFromFilter.value) this.dateFromFilter.value = today;
        if (this.dateToFilter   && !this.dateToFilter.value)   this.dateToFilter.value   = today;
        const formDate = document.getElementById('formDate');
        if (formDate && !formDate.value) formDate.value = today;
    }

    syncQuickFilterUI(status) {
        document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
        const active = document.querySelector(`.btn-filter[data-status="${status}"]`);
        if (active) active.classList.add('active');
        if (this.statusFilter) {
            this.statusFilter.value = (status === 'all' || !status) ? '' : status;
        }
        const today = todayISO();
        if (this.dateFromFilter) this.dateFromFilter.value = today;
        if (this.dateToFilter)   this.dateToFilter.value   = today;
    }

    // ── Table rendering ──────────────────────────
    showTableLoading() {
        const tbody = document.querySelector('#attendanceTable tbody');
        const colCount = document.querySelector('thead tr')?.querySelectorAll('th').length || 11;
        if (tbody) tbody.innerHTML =
            `<tr><td colspan="${colCount}" class="text-center">
                <i class="fas fa-spinner fa-spin"></i> Loading...
             </td></tr>`;
    }

    renderRows(records, pagination = null) {
        const tbody = document.querySelector('#attendanceTable tbody');
        if (!tbody) return;

        const headerRow = document.querySelector('thead tr');
        const colCount  = headerRow?.querySelectorAll('th').length || 12;
        const isAdmin   = colCount > 9;

        if (!records || !records.length) {
            tbody.innerHTML = `<tr><td colspan="${colCount}" class="text-center">No records found</td></tr>`;
            if (pagination) this._updatePagination(pagination);
            return;
        }

        const isWeekend = dateStr => { const d = new Date(dateStr); return d.getDay() === 0 || d.getDay() === 6; };

        tbody.innerHTML = records.map(r => {
            const weekendDate   = r.is_weekend_date !== undefined ? r.is_weekend_date : isWeekend(r.date);
            const weekendStatus = r.status === 'weekend';
            const simplified    = r.simplified_status || (r.status === 'leave' ? 'leave' : 'absent');
            const simplDisplay  = r.simplified_status_display || (simplified === 'present' ? 'Present' : simplified === 'leave' ? 'Leave' : 'Absent');
            const isHoliday     = !!(r.is_holiday_date || r.holiday_name || r.status === 'holiday');
            const hasData       = (r.check_in && r.check_in !== '--') || (r.check_out && r.check_out !== '--');

            const lateBadge     = (r.status === 'late' || r.late_in > 0)
                ? `<span class="badge late">${r.late_in_display || 'Late'}</span>` : '<span class="text-muted">--</span>';
            const leaveBadge    = r.status === 'leave'
                ? `<span class="badge leave">${r.leave_type_display || 'On Leave'}</span>` : '<span class="text-muted">--</span>';
            const overtimeBadge = r.overtime_display && r.overtime_display !== '--'
                ? `<span class="badge overtime">${r.overtime_display}</span>` : '<span class="text-muted">--</span>';
            const weekendBadge  = weekendDate && hasData
                ? `<span class="badge weekend"><i class="fas fa-calendar-week"></i> Weekend</span>` : '<span class="text-muted">--</span>';
            const holidayBadge  = isHoliday
                ? `<span class="badge holiday" title="${escapeHtml(r.holiday_name || 'Holiday')}"><i class="fas fa-calendar-check"></i> Holiday</span>` : '';

            let statusCell = '';
            if (r.status === 'holiday' && !hasData) {
                statusCell = holidayBadge || `<span class="badge holiday"><i class="fas fa-calendar-check"></i> Holiday</span>`;
            } else {
                statusCell = `<span class="badge ${simplified}">${simplDisplay}</span>`;
                if (weekendDate && hasData) statusCell += ` <span class="badge weekend"><i class="fas fa-calendar-week"></i> Weekend</span>`;
                if (holidayBadge) statusCell += ` ${holidayBadge}`;
            }

            let row = `<tr class="${weekendStatus ? 'weekend-row' : ''}">`;
            if (isAdmin) {
                const code    = r.employee_code || '';
                const fname   = r.employee_firstname || (r.employee_name ? r.employee_name.split(' ')[0] : '');
                const display = `${code ? code + ' - ' : ''}${fname || r.employee_name || ''}`;
                const team    = r.team_display || r.team || '';
                const hasTeam = team && team !== 'No Team' && team.trim();
                row += `
                    <td><span class="employee-name-badge"><i class="fas fa-user" style="margin-right:.3rem;"></i>${display}</span></td>
                    <td>${hasTeam ? `<span class="team-badge"><i class="fas fa-users"></i> ${team}</span>` : '<span class="text-muted">No Team</span>'}</td>`;
            }
            row += `
                <td>${r.date}</td>
                <td>${r.check_in !== '--' ? `<span>${r.check_in}</span>` : '--'}</td>
                <td>${r.check_out !== '--' ? `<span>${r.check_out}</span>` : '--'}</td>
                <td>${statusCell}</td>
                <td>${lateBadge}</td>
                <td>${leaveBadge}</td>
                <td>${overtimeBadge}</td>
                <td>${weekendBadge}</td>
                <td>${r.duration}</td>`;
            if (isAdmin) {
                row += `
                    <td>
                        <button class="btn btn-secondary btn-sm edit-attendance" data-id="${r.id}">
                            <i class="fas fa-edit"></i>
                        </button>
                        <form action="/attendance/delete/${r.id}/" method="POST" style="display:inline;">
                            <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(this.csrfToken)}">
                            <button type="submit" class="btn btn-danger btn-sm"
                                    onclick="return confirm('Delete this record?')">
                                <i class="fas fa-trash"></i>
                            </button>
                        </form>
                    </td>`;
            }
            row += '</tr>';
            return row;
        }).join('');

        if (pagination) this._updatePagination(pagination);
    }

    _updatePagination(p) {
        const info = document.querySelector('.pagination-controls span');
        if (info && p) {
            const start = p.total_count > 0 ? (p.current_page - 1) * p.per_page + 1 : 0;
            const end   = Math.min(p.current_page * p.per_page, p.total_count);
            info.textContent = `Showing ${start} - ${end} of ${p.total_count}`;
        }
        const sel = document.getElementById('perPageSelect');
        if (sel && p?.per_page) sel.value = p.per_page;

        let wrapper = document.querySelector('.pagination-wrapper');
        if (!wrapper) {
            const tableContainer = document.querySelector('.table-container');
            if (!tableContainer?.parentNode) return;
            wrapper = document.createElement('div');
            wrapper.className = 'pagination-wrapper';
            wrapper.style.cssText = 'margin-top:1.5rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem;';
            tableContainer.parentNode.insertBefore(wrapper, tableContainer.nextSibling);
        }
        if (!p || p.total_pages <= 1) { wrapper.style.display = 'none'; return; }
        wrapper.style.display = 'flex';

        const nav = document.createElement('nav');
        nav.className = 'pagination';
        nav.style.cssText = 'display:flex;gap:.5rem;';

        const mkBtn = (label, page, icon, enabled, iconBefore = true) => {
            const el = document.createElement(enabled ? 'button' : 'span');
            el.className = 'btn btn-secondary btn-sm';
            if (!enabled) el.style.cssText = 'opacity:.5;cursor:not-allowed;';
            const ico = `<i class="${icon}"></i>`;
            el.innerHTML = iconBefore ? `${ico} ${label}` : `${label} ${ico}`;
            if (enabled && page) el.onclick = () => this.emit('attendance:goToPage', page);
            return el;
        };

        nav.appendChild(mkBtn('First',    1,               'fas fa-angle-double-left',  p.has_previous));
        nav.appendChild(mkBtn('Previous', p.current_page-1,'fas fa-angle-left',         p.has_previous));

        const start = Math.max(1, p.current_page - 2);
        const end   = Math.min(p.total_pages, p.current_page + 2);
        for (let i = start; i <= end; i++) {
            const btn = document.createElement('button');
            btn.className = i === p.current_page ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm';
            btn.textContent = i;
            if (i !== p.current_page) btn.onclick = () => this.emit('attendance:goToPage', i);
            nav.appendChild(btn);
        }
        nav.appendChild(mkBtn('Next', p.current_page+1, 'fas fa-angle-right',       p.has_next, false));
        nav.appendChild(mkBtn('Last', p.total_pages,    'fas fa-angle-double-right', p.has_next, false));

        const pInfo = document.createElement('div');
        pInfo.style.cssText = 'font-size:.9rem;color:var(--text-light);';
        pInfo.textContent = `Page ${p.current_page} of ${p.total_pages}`;

        wrapper.innerHTML = '';
        wrapper.appendChild(pInfo);
        wrapper.appendChild(nav);
    }

    showFilterCount(count) {
        document.querySelector('.filter-count-badge')?.remove();
        if (count > 0 && this.toggleFiltersBtn) {
            const badge = document.createElement('span');
            badge.className = 'filter-count-badge';
            badge.textContent = count;
            badge.style.cssText = 'background:#e74c3c;color:white;border-radius:10px;padding:2px 6px;font-size:.7rem;margin-left:5px;';
            this.toggleFiltersBtn.appendChild(badge);
        }
    }

    collectFilterParams() {
        const p = new URLSearchParams();
        if (this.employeeFilter?.value?.trim()) p.append('employee', this.employeeFilter.value.trim());
        if (this.dateFromFilter?.value)         p.append('date_from', this.dateFromFilter.value);
        if (this.dateToFilter?.value)           p.append('date_to',   this.dateToFilter.value);
        if (this.statusFilter?.value && this.statusFilter.value !== 'all')
            p.append('status', this.statusFilter.value);
        const team = this.teamFilter?.value || this.statusFilterTeam?.value;
        if (team) p.append('team', team);
        const perPage = document.getElementById('perPageSelect')?.value || '50';
        p.append('per_page', perPage);
        return p;
    }
}
