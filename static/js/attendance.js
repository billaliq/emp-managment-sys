document.addEventListener('DOMContentLoaded', function () {
    console.log('Attendance JS loaded');

    // Get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');

    const markAttendanceBtn = document.getElementById('markAttendanceBtn');
    const markAttendanceModal = document.getElementById('markAttendanceModal');
    const closeMarkAttendanceModal = document.getElementById('closeMarkAttendanceModal');
    const cancelMarkAttendance = document.getElementById('cancelMarkAttendance');
    const attendanceForm = document.getElementById('attendanceForm');
    const formStatus = document.getElementById('formStatus');
    const leaveTypeGroup = document.getElementById('leaveTypeGroup');
    const toggleFiltersBtn = document.getElementById('toggleFiltersBtn');
    const filterSection = document.getElementById('filterSection');
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');
    const teamFilter = document.getElementById('teamFilter');
    const statusFilterTeam = document.getElementById('statusFilterTeam');

    // Modal functions
    function openModal() {
        markAttendanceModal.classList.add('active');
    }

    function closeModal() {
        markAttendanceModal.classList.remove('active');
        attendanceForm.reset();
        document.getElementById('attendanceId').value = "";
        attendanceForm.action = "/attendance/mark/";
        // Hide leave type field when modal closes
        if (leaveTypeGroup) leaveTypeGroup.style.display = 'none';
    }

    // Show/hide leave type field based on status selection
    function toggleLeaveTypeField() {
        if (formStatus && leaveTypeGroup) {
            if (formStatus.value === 'leave') {
                leaveTypeGroup.style.display = 'block';
            } else {
                leaveTypeGroup.style.display = 'none';
                // Clear leave type when status changes
                const leaveTypeSelect = document.getElementById('formLeaveType');
                if (leaveTypeSelect) leaveTypeSelect.value = '';
            }
        }
    }

    // Toggle filters visibility
    function toggleFilters() {
        if (filterSection.style.display === 'none' || !filterSection.style.display) {
            filterSection.style.display = 'block';
            toggleFiltersBtn.innerHTML = '<i class="fas fa-times"></i> Hide Filters';
            toggleFiltersBtn.classList.add('active');
        } else {
            filterSection.style.display = 'none';
            toggleFiltersBtn.innerHTML = '<i class="fas fa-filter"></i> Filters';
            toggleFiltersBtn.classList.remove('active');
        }
    }

    // Clear all filters
    function clearFilters() {
        if (employeeFilter) employeeFilter.value = '';
        if (dateFromFilter) dateFromFilter.value = '';
        if (dateToFilter) dateToFilter.value = '';
        if (statusFilter) statusFilter.value = '';

        // Clear team filters
        if (teamFilter) teamFilter.value = '';
        if (statusFilterTeam) statusFilterTeam.value = '';

        // Reset quick filters
        document.querySelectorAll('.btn-filter').forEach(btn => {
            btn.classList.remove('active');
        });
        const allFilterBtn = document.querySelector('.btn-filter[data-status="all"]');
        if (allFilterBtn) allFilterBtn.classList.add('active');

        // Clear URL parameters and reload
        const url = new URL(window.location);
        url.search = ''; // Clear all query parameters
        window.location.href = url.toString();
    }

    // Event listeners
    if (markAttendanceBtn) {
        markAttendanceBtn.addEventListener('click', () => {
            document.getElementById('attendanceId').value = "";
            attendanceForm.action = "/attendance/mark/";
            openModal();
        });
    }

    if (closeMarkAttendanceModal) {
        closeMarkAttendanceModal.addEventListener('click', closeModal);
    }

    if (cancelMarkAttendance) {
        cancelMarkAttendance.addEventListener('click', closeModal);
    }

    // Show/hide leave type field based on status selection
    if (formStatus && leaveTypeGroup) {
        formStatus.addEventListener('change', toggleLeaveTypeField);
        // Check initial state
        toggleLeaveTypeField();
    }

    if (toggleFiltersBtn) {
        toggleFiltersBtn.addEventListener('click', toggleFilters);
    }

    if (clearFiltersBtn) {
        clearFiltersBtn.addEventListener('click', clearFilters);
    }

    // ==============================
    // Quick Filter Buttons
    // ==============================
    const quickFilterButtons = document.querySelectorAll('.btn-filter');

    quickFilterButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active class from all buttons
            quickFilterButtons.forEach(btn => btn.classList.remove('active'));

            // Add active class to clicked button
            this.classList.add('active');

            const status = this.dataset.status;
            applyQuickFilter(status);
        });
    });

    function applyQuickFilter(status) {
        const params = new URLSearchParams();

        // For "all" status, don't add status parameter (shows all statuses)
        // For other statuses, add the status filter
        if (status && status !== 'all') {
            params.append('status', status);
        }

        // For all quick filters, set date range to today
        // This ensures quick filters show today's attendance
        const today = new Date().toISOString().split('T')[0];
        params.append('date_from', today);
        params.append('date_to', today);

        // Preserve team filter if it's set (check both team filter locations)
        const activeTeamFilter = (teamFilter && teamFilter.value) || (statusFilterTeam && statusFilterTeam.value);
        if (activeTeamFilter) {
            params.append('team', activeTeamFilter);
        }

        // Update the date filter inputs to reflect today's date
        if (dateFromFilter) {
            dateFromFilter.value = today;
        }
        if (dateToFilter) {
            dateToFilter.value = today;
        }

        // Update status filter dropdown if it exists
        if (statusFilter) {
            if (status === 'all' || !status) {
                statusFilter.value = '';
            } else {
                statusFilter.value = status;
            }
        }

        console.log('Applying quick filter:', status, 'with params:', params.toString());
        fetchFiltered(params);
    }

    // ==============================
    // Editing attendance records
    // ==============================
    function bindEditButtons() {
        document.querySelectorAll('.edit-attendance').forEach(btn => {
            btn.addEventListener('click', function () {
                const id = this.dataset.id;
                console.log('Editing attendance ID:', id);

                fetch(`/attendance/json/${id}/`)
                    .then(res => {
                        if (!res.ok) {
                            throw new Error('Network response was not ok: ' + res.status);
                        }
                        return res.json();
                    })
                    .then(data => {
                        console.log('Edit data:', data);
                        document.getElementById('attendanceId').value = data.id;
                        document.getElementById('formEmployee').value = data.employee_id;
                        document.getElementById('formDate').value = data.date;
                        document.getElementById('formCheckIn').value = data.check_in;
                        document.getElementById('formCheckOut').value = data.check_out;
                        // Use simplified_status (present/absent/leave) for the form dropdown
                        const statusValue = data.status === 'leave' ? 'leave' : (data.status || 'present');
                        document.getElementById('formStatus').value = statusValue;
                        document.getElementById('formOvertime').value = data.overtime_hours;
                        document.getElementById('formNotes').value = data.notes;
                        // Set leave type if status is leave
                        if (data.status === 'leave' && data.leave_type) {
                            const leaveTypeSelect = document.getElementById('formLeaveType');
                            if (leaveTypeSelect) leaveTypeSelect.value = data.leave_type;
                        }
                        // Toggle leave type field visibility
                        if (formStatus && leaveTypeGroup) {
                            toggleLeaveTypeField();
                        }
                        attendanceForm.action = `/attendance/update/${id}/`;
                        openModal();
                    })
                    .catch(error => {
                        console.error('Error fetching attendance data:', error);
                        alert('Error loading attendance data: ' + error.message);
                    });
            });
        });
    }
    bindEditButtons();

    // ==============================
    // Advanced filter (AJAX-backed)
    // ==============================
    const filterForm = document.getElementById('attendanceFilterForm');
    const employeeFilter = document.getElementById('employeeFilter');
    const dateFromFilter = document.getElementById('dateFromFilter');
    const dateToFilter = document.getElementById('dateToFilter');
    const statusFilter = document.getElementById('statusFilter');

    function renderRows(records, pagination = null) {
        const tbody = document.querySelector('#attendanceTable tbody');
        if (!tbody) {
            console.error('Table body not found');
            return;
        }

        // Determine column count based on table headers
        const headerRow = document.querySelector('thead tr');
        const colCount = headerRow ? headerRow.querySelectorAll('th').length : 12;

        if (!records || records.length === 0) {
            tbody.innerHTML = `<tr><td colspan="${colCount}" class="text-center">No records found</td></tr>`;
            if (pagination) {
                updatePaginationControls(pagination);
            }
            return;
        }

        // Check if we're in admin view (has Actions column)
        const isAdminView = colCount > 9;

        // Helper function to check if date is weekend
        function isWeekendDate(dateString) {
            const date = new Date(dateString);
            const day = date.getDay();
            return day === 0 || day === 6; // Sunday = 0, Saturday = 6
        }

        // Basic HTML escaping for tooltip/title strings
        function escapeHtml(value) {
            if (value === null || value === undefined) return '';
            return String(value)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        const rowsHtml = records.map(r => {
            // Show weekend badge on employee name if date is weekend (regardless of status)
            // Use backend property if available, otherwise check date
            const isWeekendDateCheck = r.is_weekend_date !== undefined ? r.is_weekend_date : (r.is_weekend || isWeekendDate(r.date));
            const weekendLabelOnName = isWeekendDateCheck ? '<span class="weekend-label"><i class="fas fa-calendar-week"></i> Weekend</span>' : '';

            // Only show weekend badge on status if status is 'weekend'
            const isWeekendStatus = r.status === 'weekend';
            const weekendLabelOnStatus = isWeekendStatus ? '<span class="weekend-label"><i class="fas fa-calendar-week"></i> Weekend</span>' : '';

            let rowHtml = `<tr class="${isWeekendStatus ? 'weekend-row' : ''}">`;

            // Add Employee and Team columns only for admin view
            if (isAdminView) {
                const employeeCode = r.employee_code || '';
                const employeeFirst = r.employee_firstname || (r.employee_name ? r.employee_name.split(' ')[0] : '');
                const employeeFull = r.employee_name || '';
                const employeeDisplay = `${employeeCode ? employeeCode + ' - ' : ''}${employeeFirst || employeeFull}`;
                const teamDisplay = r.team_display || r.team || '';
                const hasValidTeam = teamDisplay && teamDisplay !== 'No Team' && teamDisplay !== '-- Select Team --' && teamDisplay.trim() !== '';

                rowHtml += `
                <td>
                    <span class="employee-name-badge">
                        <i class="fas fa-user" style="margin-right: 0.3rem;"></i>
                        ${employeeDisplay}
                    </span>
                    ${weekendLabelOnName}
                </td>
                <td>
                    ${hasValidTeam
                        ? `<span class="team-badge" title="Team: ${teamDisplay}"><i class="fas fa-users"></i> ${teamDisplay}</span>`
                        : '<span class="text-muted">No Team</span>'}
                </td>`;
            }

            // Determine simplified status (Present, Absent, or Leave) - use backend value if available
            const simplifiedStatus = r.simplified_status !== undefined ? r.simplified_status :
                (r.status === 'leave' ? 'leave' :
                 (r.status === 'present' || r.status === 'late' || r.status === 'early-in' ||
                  r.status === 'early-out' || r.status === 'overtime' || r.status === 'late-sitting' ||
                  (r.status === 'weekend' && (r.check_in || r.check_out))) ? 'present' :
                 'absent');
            const simplifiedStatusDisplay = r.simplified_status_display !== undefined ? r.simplified_status_display :
                (simplifiedStatus === 'present' ? 'Present' :
                 simplifiedStatus === 'leave' ? 'Leave' : 'Absent');

            // Determine Late status
            const lateDisplay = (r.status === 'late' || (r.late_in && r.late_in > 0)) ?
                `<span class="badge late">${r.late_in_display || 'Late'}</span>` :
                '<span class="text-muted">--</span>';

            // Determine Leave status
            const leaveDisplay = (r.status === 'leave') ?
                `<span class="badge leave">${r.leave_type_display || 'On Leave'}</span>` :
                '<span class="text-muted">--</span>';

            // Determine Overtime status
            const overtimeDisplay = (r.overtime_display && r.overtime_display !== '--' && parseFloat(r.overtime_display.replace(/[^0-9.]/g, '')) > 0) || r.status === 'overtime' ?
                `<span class="badge overtime">${r.overtime_display || 'Overtime'}</span>` :
                '<span class="text-muted">--</span>';

            // Determine Weekend status
            const hasAttendanceData = (r.check_in && r.check_in !== '--') || (r.check_out && r.check_out !== '--');
            const weekendDisplay = (isWeekendDateCheck && hasAttendanceData) ?
                `<span class="badge weekend"><i class="fas fa-calendar-week"></i> Weekend</span>` :
                '<span class="text-muted">--</span>';

            // Holiday badge (from backend Holiday config)
            const isHolidayDate = !!(r.is_holiday_date || r.holiday_name || r.status === 'holiday');
            const holidayName = r.holiday_name || '';
            const holidayBadge = isHolidayDate
                ? `<span class="badge holiday" title="${escapeHtml(holidayName || 'Holiday')}"><i class="fas fa-calendar-check"></i> Holiday</span>`
                : '';

            // Status cell: show Holiday-only for holiday records without attendance, otherwise show simplified status + optional Weekend/Holiday badges
            let statusCellHtml = '';
            if (r.status === 'holiday' && !hasAttendanceData) {
                statusCellHtml = holidayBadge || `<span class="badge holiday"><i class="fas fa-calendar-check"></i> Holiday</span>`;
            } else {
                statusCellHtml = `<span class="badge ${simplifiedStatus}">${simplifiedStatusDisplay}</span>`;
                if (isWeekendDateCheck && hasAttendanceData) {
                    statusCellHtml += ` <span class="badge weekend"><i class="fas fa-calendar-week"></i> Weekend</span>`;
                }
                if (holidayBadge) {
                    statusCellHtml += ` ${holidayBadge}`;
                }
            }

            rowHtml += `
                <td>
                    ${r.date}
                </td>
                <td>
                    ${r.check_in !== '--' ?
                        `<span>${r.check_in}</span>` :
                        '--'
                    }
                </td>
                <td>
                    ${r.check_out !== '--' ?
                        `<span>${r.check_out}</span>` :
                        '--'
                    }
                </td>
                <td>
                    ${statusCellHtml}
                </td>
                <td>${lateDisplay}</td>
                <td>${leaveDisplay}</td>
                <td>${overtimeDisplay}</td>
                <td>${weekendDisplay}</td>
                <td>${r.duration}</td>`;

            // Add Actions column only for admin view
            if (isAdminView) {
                rowHtml += `
                <td>
                    <button class="btn btn-secondary btn-sm edit-attendance" data-id="${r.id}">
                        <i class="fas fa-edit"></i>
                    </button>
                    <form action="/attendance/delete/${r.id}/" method="POST" style="display:inline;">
                        <input type="hidden" name="csrfmiddlewaretoken" value="${csrftoken}">
                        <button type="submit" class="btn btn-danger btn-sm" onclick="return confirm('Delete this record?')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </form>
                </td>`;
            }

            rowHtml += `</tr>`;

            return rowHtml;
        }).join('');

        tbody.innerHTML = rowsHtml;

        // Re-bind edit buttons for newly rendered rows
        bindEditButtons();

        // Update pagination controls if provided
        if (pagination) {
            updatePaginationControls(pagination);
        }
    }

    function updatePaginationControls(pagination) {
        // Update the "Showing X - Y of Z" text
        const showingText = document.querySelector('.pagination-controls span');
        if (showingText && pagination) {
            const start = pagination.total_count > 0 ? (pagination.current_page - 1) * pagination.per_page + 1 : 0;
            const end = Math.min(pagination.current_page * pagination.per_page, pagination.total_count);
            showingText.textContent = `Showing ${start} - ${end} of ${pagination.total_count}`;
        }

        // Update per_page selector if it exists
        const perPageSelect = document.getElementById('perPageSelect');
        if (perPageSelect && pagination && pagination.per_page) {
            perPageSelect.value = pagination.per_page;
        }

        // Update pagination buttons
        renderPaginationButtons(pagination);
    }

    function renderPaginationButtons(pagination) {
        if (!pagination) return;

        // Find or create pagination wrapper
        let paginationWrapper = document.querySelector('.pagination-wrapper');
        if (!paginationWrapper) {
            // Create pagination wrapper if it doesn't exist
            const tableContainer = document.querySelector('.table-container');
            if (tableContainer && tableContainer.parentNode) {
                paginationWrapper = document.createElement('div');
                paginationWrapper.className = 'pagination-wrapper';
                paginationWrapper.style.cssText = 'margin-top: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;';
                tableContainer.parentNode.insertBefore(paginationWrapper, tableContainer.nextSibling);
            } else {
                return;
            }
        }

        // Only show pagination if there are multiple pages
        if (pagination.total_pages <= 1) {
            paginationWrapper.style.display = 'none';
            return;
        }
        paginationWrapper.style.display = 'flex';

        // Build pagination info
        const paginationInfo = document.createElement('div');
        paginationInfo.className = 'pagination-info';
        paginationInfo.style.cssText = 'font-size: 0.9rem; color: var(--text-light);';
        paginationInfo.textContent = `Page ${pagination.current_page} of ${pagination.total_pages}`;

        // Build pagination nav
        const paginationNav = document.createElement('nav');
        paginationNav.className = 'pagination';
        paginationNav.style.cssText = 'display: flex; gap: 0.5rem;';

        // First button
        if (pagination.has_previous) {
            const firstBtn = createPaginationButton('First', 1, 'fas fa-angle-double-left', true);
            paginationNav.appendChild(firstBtn);
        } else {
            const firstBtn = createPaginationButton('First', null, 'fas fa-angle-double-left', false);
            paginationNav.appendChild(firstBtn);
        }

        // Previous button
        if (pagination.has_previous) {
            const prevBtn = createPaginationButton('Previous', pagination.current_page - 1, 'fas fa-angle-left', true);
            paginationNav.appendChild(prevBtn);
        } else {
            const prevBtn = createPaginationButton('Previous', null, 'fas fa-angle-left', false);
            paginationNav.appendChild(prevBtn);
        }

        // Page number buttons
        const startPage = Math.max(1, pagination.current_page - 2);
        const endPage = Math.min(pagination.total_pages, pagination.current_page + 2);

        for (let i = startPage; i <= endPage; i++) {
            const pageBtn = document.createElement('button');
            pageBtn.className = i === pagination.current_page ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm';
            pageBtn.textContent = i;
            if (i !== pagination.current_page) {
                pageBtn.onclick = () => goToPage(i);
            }
            paginationNav.appendChild(pageBtn);
        }

        // Next button
        if (pagination.has_next) {
            const nextBtn = createPaginationButton('Next', pagination.current_page + 1, 'fas fa-angle-right', true, false);
            paginationNav.appendChild(nextBtn);
        } else {
            const nextBtn = createPaginationButton('Next', null, 'fas fa-angle-right', false, false);
            paginationNav.appendChild(nextBtn);
        }

        // Last button
        if (pagination.has_next) {
            const lastBtn = createPaginationButton('Last', pagination.total_pages, 'fas fa-angle-double-right', true, false);
            paginationNav.appendChild(lastBtn);
        } else {
            const lastBtn = createPaginationButton('Last', null, 'fas fa-angle-double-right', false, false);
            paginationNav.appendChild(lastBtn);
        }

        // Clear and update wrapper
        paginationWrapper.innerHTML = '';
        paginationWrapper.appendChild(paginationInfo);
        paginationWrapper.appendChild(paginationNav);
    }

    function createPaginationButton(text, page, iconClass, enabled, iconBefore = true) {
        const btn = document.createElement(enabled ? 'button' : 'span');
        btn.className = 'btn btn-secondary btn-sm';
        if (!enabled) {
            btn.style.cssText = 'opacity: 0.5; cursor: not-allowed;';
        }

        const icon = document.createElement('i');
        icon.className = iconClass;

        if (iconBefore) {
            btn.appendChild(icon);
            btn.appendChild(document.createTextNode(' ' + text));
        } else {
            btn.appendChild(document.createTextNode(text + ' '));
            btn.appendChild(icon);
        }

        if (enabled && page) {
            btn.onclick = () => goToPage(page);
        }

        return btn;
    }

    function goToPage(page) {
        // Get current filter parameters
        const searchParams = new URLSearchParams();

        // Employee search
        if (employeeFilter && employeeFilter.value && employeeFilter.value.trim()) {
            searchParams.append('employee', employeeFilter.value.trim());
        }

        // Date filters
        if (dateFromFilter && dateFromFilter.value) {
            searchParams.append('date_from', dateFromFilter.value);
        }
        if (dateToFilter && dateToFilter.value) {
            searchParams.append('date_to', dateToFilter.value);
        }

        // Status filter
        if (statusFilter && statusFilter.value && statusFilter.value !== 'all') {
            searchParams.append('status', statusFilter.value);
        }

        // Team filter
        const activeTeamFilter = (teamFilter && teamFilter.value) || (statusFilterTeam && statusFilterTeam.value);
        if (activeTeamFilter) {
            searchParams.append('team', activeTeamFilter);
        }

        // Per page
        const perPageSelect = document.getElementById('perPageSelect');
        if (perPageSelect && perPageSelect.value) {
            searchParams.append('per_page', perPageSelect.value);
        } else {
            searchParams.append('per_page', '50');
        }

        // Page
        searchParams.append('page', page.toString());

        // Fetch filtered data
        fetchFiltered(searchParams);
    }

    async function fetchFiltered(params = null) {
        let searchParams;

        if (params) {
            // Use provided params (from quick filter or pagination)
            searchParams = params;

            // Still add per_page from current state if not already set
            if (!searchParams.has('per_page')) {
                const perPageSelect = document.getElementById('perPageSelect');
                if (perPageSelect && perPageSelect.value) {
                    searchParams.set('per_page', perPageSelect.value);
                } else {
                    const urlParams = new URLSearchParams(window.location.search);
                    const perPage = urlParams.get('per_page') || '50';
                    searchParams.set('per_page', perPage);
                }
            }
            // Only reset to page 1 if page is not already set (new filter, not pagination)
            if (!searchParams.has('page')) {
                searchParams.set('page', '1');
            }
        } else {
            // Build params from form inputs
            searchParams = new URLSearchParams();

            // Employee search (only if has value)
            if (employeeFilter && employeeFilter.value && employeeFilter.value.trim()) {
                searchParams.append('employee', employeeFilter.value.trim());
            }

            // Date filters (only if has value)
            if (dateFromFilter && dateFromFilter.value) {
                searchParams.append('date_from', dateFromFilter.value);
            }
            if (dateToFilter && dateToFilter.value) {
                searchParams.append('date_to', dateToFilter.value);
            }

            // Status filter (only if not 'all' or empty)
            if (statusFilter && statusFilter.value && statusFilter.value !== 'all') {
                searchParams.append('status', statusFilter.value);
            }

            // Team filter (check both locations, prioritize teamFilter)
            const activeTeamFilter = (teamFilter && teamFilter.value) || (statusFilterTeam && statusFilterTeam.value);
            if (activeTeamFilter) {
                searchParams.append('team', activeTeamFilter);
            }

            // Per page parameter
            const perPageSelect = document.getElementById('perPageSelect');
            if (perPageSelect && perPageSelect.value) {
                searchParams.append('per_page', perPageSelect.value);
            } else {
                const urlParams = new URLSearchParams(window.location.search);
                const perPage = urlParams.get('per_page') || '50';
                searchParams.append('per_page', perPage);
            }

            // Page parameter - reset to 1 when applying new filters
            searchParams.append('page', '1');
        }

        console.log('Fetching filtered data with params:', searchParams.toString());

        // Show loading state
        const tbody = document.querySelector('#attendanceTable tbody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="' + (document.querySelector('thead tr') ? document.querySelector('thead tr').querySelectorAll('th').length : 11) + '" class="text-center"><i class="fas fa-spinner fa-spin"></i> Loading...</td></tr>';
        }

        try {
            const res = await fetch(`/attendance/filter-ajax/?${searchParams.toString()}`);
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            const data = await res.json();
            console.log('Filtered data received:', data);

            if (data.records) {
                renderRows(data.records, data.pagination);
                showFilterCount(data.pagination ? data.pagination.total_count : data.records.length);
            } else {
                console.error('No records in response:', data);
                renderRows([], data.pagination || { current_page: 1, total_pages: 1, total_count: 0, has_previous: false, has_next: false, per_page: 50 });
            }
        } catch (error) {
            console.error('Error fetching filtered data:', error);
            alert('Error loading filtered data. Please check console for details.');
        }
    }

    function showFilterCount(count) {
        // Remove existing count badge
        const existingBadge = document.querySelector('.filter-count-badge');
        if (existingBadge) {
            existingBadge.remove();
        }

        // Add count badge to filter button
        if (count > 0) {
            const badge = document.createElement('span');
            badge.className = 'filter-count-badge';
            badge.textContent = count;
            badge.style.cssText = `
                background: #e74c3c;
                color: white;
                border-radius: 10px;
                padding: 2px 6px;
                font-size: 0.7rem;
                margin-left: 5px;
            `;
            toggleFiltersBtn.appendChild(badge);
        }
    }

    if (filterForm) {
        filterForm.addEventListener('submit', function (e) {
            e.preventDefault();
            console.log('Filter form submitted');
            fetchFiltered();
        });
    }

    // Debounce helper for typing in Employee search
    function debounce(fn, delay) {
        let t;
        return function (...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    // Auto-apply filters when inputs change
    if (employeeFilter) {
        employeeFilter.addEventListener('input', debounce(fetchFiltered, 500));
    }
    if (dateFromFilter) {
        dateFromFilter.addEventListener('change', fetchFiltered);
    }
    if (dateToFilter) {
        dateToFilter.addEventListener('change', fetchFiltered);
    }
    if (statusFilter) {
        statusFilter.addEventListener('change', fetchFiltered);
    }

    // Team filter event listeners
    if (teamFilter) {
        teamFilter.addEventListener('change', function() {
            // Use AJAX to filter instead of reloading page
            fetchFiltered();
        });
    }

    if (statusFilterTeam) {
        statusFilterTeam.addEventListener('change', fetchFiltered);
    }

    // Auto-fill today's date in the modal
    const today = new Date().toISOString().split('T')[0];
    const formDateInput = document.getElementById('formDate');
    if (formDateInput && !formDateInput.value) {
        formDateInput.value = today;
    }

    // Auto-fill current date in date filters (not month start)
    if (dateFromFilter && !dateFromFilter.value) {
        // Set to today's date instead of month start
        dateFromFilter.value = today;
    }
    if (dateToFilter && !dateToFilter.value) {
        dateToFilter.value = today;
    }

    // Handle per page selector
    const perPageSelect = document.getElementById('perPageSelect');
    if (perPageSelect) {
        perPageSelect.addEventListener('change', function() {
            const perPage = this.value;

            // Check if filters are active (using AJAX)
            const hasActiveFilters = (employeeFilter && employeeFilter.value) ||
                                    (dateFromFilter && dateFromFilter.value) ||
                                    (dateToFilter && dateToFilter.value) ||
                                    (statusFilter && statusFilter.value) ||
                                    (teamFilter && teamFilter.value) ||
                                    (statusFilterTeam && statusFilterTeam.value);

            if (hasActiveFilters) {
                // If filters are active, use AJAX to update
                const url = new URL(window.location);
                url.searchParams.set('per_page', perPage);
                url.searchParams.set('page', '1'); // Reset to first page
                window.history.pushState({}, '', url.toString());
                fetchFiltered();
            } else {
                // If no filters, reload page with new per_page
                const url = new URL(window.location);
                url.searchParams.set('per_page', perPage);
                url.searchParams.set('page', '1'); // Reset to first page when changing per_page
                window.location.href = url.toString();
            }
        });
    }

    // Bind pagination buttons to use AJAX instead of page reload
    function bindPaginationButtons() {
        document.querySelectorAll('.pagination-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const page = parseInt(this.dataset.page);
                if (page) {
                    goToPage(page);
                }
            });
        });
    }
    bindPaginationButtons();

    // Apply filters on page load if any filter has value
    setTimeout(() => {
        if (employeeFilter?.value || dateFromFilter?.value || dateToFilter?.value || statusFilter?.value) {
            console.log('Applying filters on page load');
            fetchFiltered();
        }
    }, 100);

    // Close modal when clicking outside
    markAttendanceModal.addEventListener('click', function(e) {
        if (e.target === markAttendanceModal) {
            closeModal();
        }
    });
});