// departments.js - Fixed version with debugging

document.addEventListener('DOMContentLoaded', function () {
    console.log('Departments script loaded');

    // Elements
    const newDepartmentBtn = document.getElementById('newDepartmentBtn');
    const newDepartmentBtnEmpty = document.getElementById('newDepartmentBtnEmpty');
    const newDepartmentModal = document.getElementById('newDepartmentModal');
    const closeModal = document.getElementById('closeModal');
    const cancelBtn = document.getElementById('cancelBtn');
    const departmentForm = document.getElementById('departmentForm');
    const departmentsGrid = document.getElementById('departmentsGrid');
    const modalTitle = document.getElementById('modalTitle');
    const deptIdInput = document.getElementById('deptId');
    const submitBtn = document.getElementById('submitBtn');

    let editMode = false;
    let editingDeptId = null;

    // Office timing fields
    const useCustomTimings = document.getElementById('useCustomTimings');
    const officeTimingsFields = document.getElementById('officeTimingsFields');
    const officeStartTime = document.getElementById('officeStartTime');
    const officeEndTime = document.getElementById('officeEndTime');
    const gracePeriodMinutes = document.getElementById('gracePeriodMinutes');

    // Toggle office timing fields visibility
    function toggleOfficeTimingsFields() {
        if (useCustomTimings && officeTimingsFields) {
            if (useCustomTimings.checked) {
                officeTimingsFields.style.display = 'block';
            } else {
                officeTimingsFields.style.display = 'none';
            }
        }
    }

    // Add event listener for checkbox
    if (useCustomTimings) {
        useCustomTimings.addEventListener('change', toggleOfficeTimingsFields);
    }

    // Open modal for new department
    function openModal() {
        console.log('Opening modal');
        editMode = false;
        editingDeptId = null;
        modalTitle.textContent = "Add Department";
        departmentForm.reset();
        if (deptIdInput) deptIdInput.value = '';
        // Reset submit button text
        if (submitBtn) {
            submitBtn.innerHTML = 'Save Department';
        }
        // Reset office timings
        if (useCustomTimings) {
            useCustomTimings.checked = false;
            toggleOfficeTimingsFields();
        }
        newDepartmentModal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    // Close modal
    function closeModalFunc() {
        console.log('Closing modal');
        newDepartmentModal.classList.remove('active');
        document.body.style.overflow = 'auto';
        // Reset form and edit mode
        editMode = false;
        editingDeptId = null;
    }

    // Event listeners for opening modal
    if (newDepartmentBtn) {
        newDepartmentBtn.addEventListener('click', openModal);
    }

    if (newDepartmentBtnEmpty) {
        newDepartmentBtnEmpty.addEventListener('click', openModal);
    }

    // Event listeners for closing modal
    [closeModal, cancelBtn].forEach(btn => {
        if (btn) {
            btn.addEventListener('click', closeModalFunc);
        }
    });

    // Close modal when clicking outside
    if (newDepartmentModal) {
        newDepartmentModal.addEventListener('click', (e) => {
            if (e.target === newDepartmentModal) {
                closeModalFunc();
            }
        });
    }

    // Handle form submission
    if (departmentForm) {
        departmentForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            console.log('Form submitted');

            // Disable submit button to prevent multiple submissions
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
            }

            const formData = new FormData(departmentForm);

            // Determine URL based on mode
            let url = "/departments/create/";
            let method = "POST";

            if (editMode && editingDeptId) {
                url = `/departments/update/${editingDeptId}/`;
                method = "POST";
            }

            try {
                console.log('Sending request to:', url);
                console.log('Form data:', Object.fromEntries(formData));

                // Get CSRF token from form or cookie
                const csrfToken = departmentForm.querySelector('[name=csrfmiddlewaretoken]')?.value || getCookie("csrftoken");
                if (!csrfToken) {
                    console.error('CSRF token not found!');
                    showNotification("Security token missing. Please refresh the page and try again.", 'error');
                    return;
                }

                const response = await fetch(url, {
                    method: method,
                    body: formData,
                    headers: {
                        "X-CSRFToken": csrfToken,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                });

                console.log('Response status:', response.status, response.statusText);

                // Check if response is JSON
                const contentType = response.headers.get("content-type");
                if (!contentType || !contentType.includes("application/json")) {
                    const text = await response.text();
                    console.error('Non-JSON response:', text);
                    showNotification(`Server error: ${response.status} ${response.statusText}`, 'error');
                    return;
                }

                const data = await response.json();
                console.log('Response received:', data);

                if (response.ok && data.success) {
                    if (editMode) {
                        // Update existing department card
                        updateDepartmentCard(data.department);
                        showNotification('Department updated successfully!', 'success');
                        // Update stats after update
                        updateStats();
                    } else {
                        // Reload page to get fresh data from database
                        showNotification('Department created successfully! Reloading...', 'success');
                        setTimeout(() => {
                            window.location.reload();
                        }, 1000);
                    }
                    closeModalFunc();
                } else {
                    const errorMsg = data.error || data.message || "Something went wrong.";
                    console.error('Error from server:', errorMsg);
                    showNotification(errorMsg, 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showNotification("An error occurred while processing your request: " + error.message, 'error');
            } finally {
                // Re-enable submit button
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = editMode ? 'Update Department' : 'Save Department';
                }
            }
        });
    }

    // Function to add new department card
    function addDepartmentCard(department) {
        console.log('Adding new department card:', department);

        // Remove empty state if it exists
        const emptyState = document.getElementById('emptyState');
        if (emptyState) {
            emptyState.remove();
        }

        // Create new card HTML
        const newCard = document.createElement('div');
        newCard.className = 'department-card fade-in-up';
        newCard.setAttribute('data-id', department.id);
        newCard.innerHTML = `
            <div class="department-header">
                <div class="department-icon"><i class="fas fa-building"></i></div>
                <span class="department-status badge ${department.status === 'active' ? 'success' : 'danger'}">
                    ${department.status.charAt(0).toUpperCase() + department.status.slice(1)}
                </span>
            </div>
            <h3 class="department-title">${department.name}</h3>
            <p class="department-description">${department.description || 'No description provided'}</p>
            <div class="department-details">
                <p><strong>Employees:</strong> <span class="employee-count">0</span></p>
                <p><strong>Department Head:</strong> ${department.head_name || 'Not assigned'}</p>
                <p><strong>Date Added:</strong> ${formatDate(department.created_at)}</p>
                <p><strong>Last Updated:</strong> ${formatDate(department.updated_at)}</p>
            </div>
            <div class="department-actions">
                <button class="btn btn-success edit-btn" data-id="${department.id}"><i class="fas fa-edit"></i> Edit</button>
                <button class="btn btn-danger delete-btn" data-id="${department.id}"><i class="fas fa-trash"></i> Delete</button>
            </div>
        `;

        // Add to the grid (prepend to show at top)
        departmentsGrid.prepend(newCard);

        // Add animation
        setTimeout(() => {
            newCard.style.opacity = '1';
            newCard.style.transform = 'translateY(0)';
        }, 100);
    }

    // Function to update existing department card
    function updateDepartmentCard(department) {
        console.log('Updating department card:', department);
        const card = document.querySelector(`.department-card[data-id="${department.id}"]`);
        if (card) {
            // Update name
            const titleElement = card.querySelector('.department-title');
            if (titleElement) {
                titleElement.textContent = department.name;
            }

            // Update description
            const descElement = card.querySelector('.department-description');
            if (descElement) {
                descElement.textContent = department.description || 'No description provided';
            }

            // Update status badge
            const statusBadge = card.querySelector('.department-status');
            if (statusBadge) {
                statusBadge.textContent = department.status.charAt(0).toUpperCase() + department.status.slice(1);
                statusBadge.className = `department-status badge ${department.status === 'active' ? 'success' : 'danger'}`;
            }

            // Update employee count
            const employeeCountElement = card.querySelector('.employee-count');
            if (employeeCountElement && department.employee_count !== undefined) {
                employeeCountElement.textContent = department.employee_count;
            }

            // Update department head - handle both head object and head_name string
            const headInfo = card.querySelector('.department-details p:nth-child(2)');
            if (headInfo) {
                let headName = 'Not assigned';
                if (department.head) {
                    if (typeof department.head === 'string') {
                        headName = department.head;
                    } else if (department.head.firstname) {
                        headName = `${department.head.firstname} ${department.head.lastname || ''}`.trim();
                    }
                } else if (department.head_name) {
                    headName = department.head_name;
                }
                headInfo.innerHTML = `<strong>Department Head:</strong> ${headName}`;
            }

            // Update last updated date
            const updatedDate = card.querySelector('.department-details p:nth-child(4)');
            if (updatedDate && department.updated_at) {
                updatedDate.innerHTML = `<strong>Last Updated:</strong> ${formatDate(department.updated_at)}`;
            }
        }
    }

    // Edit department
    async function setupEditDepartment(card, deptId) {
        console.log('Setting up edit for department:', deptId);
        editMode = true;
        editingDeptId = deptId;
        modalTitle.textContent = "Edit Department";

        // Update submit button text
        if (submitBtn) {
            submitBtn.innerHTML = 'Update Department';
        }

        // Fill form with current data from card (basic info)
        document.getElementById('deptName').value = card.querySelector('.department-title').textContent;
        document.getElementById('deptDescription').value = card.querySelector('.department-description').textContent;

        const statusText = card.querySelector('.department-status').textContent.toLowerCase();
        document.getElementById('deptStatus').value = statusText;

        if (deptIdInput) deptIdInput.value = deptId;

        // Fetch full department data to get head ID and office timings
        try {
            // Get CSRF token from form or cookie
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || getCookie("csrftoken");

            const response = await fetch(`/departments/${deptId}/`, {
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest",
                },
            });
            const data = await response.json();
            if (data.head && data.head.id) {
                document.getElementById('deptHead').value = data.head.id;
            } else {
                document.getElementById('deptHead').value = '';
            }

            // Populate office timing fields
            if (useCustomTimings && data.use_custom_timings) {
                useCustomTimings.checked = true;
                toggleOfficeTimingsFields();

                if (officeStartTime && data.office_start_time) {
                    officeStartTime.value = data.office_start_time;
                }
                if (officeEndTime && data.office_end_time) {
                    officeEndTime.value = data.office_end_time;
                }
                if (gracePeriodMinutes && data.grace_period_minutes) {
                    gracePeriodMinutes.value = data.grace_period_minutes;
                }
            } else {
                useCustomTimings.checked = false;
                toggleOfficeTimingsFields();
            }
        } catch (error) {
            console.error('Error fetching department data:', error);
            // If fetch fails, just continue without setting head
            document.getElementById('deptHead').value = '';
        }

        // Open modal
        newDepartmentModal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    // Delete department
    async function deleteDepartment(deptId, card) {
        console.log('Deleting department:', deptId);
        const departmentName = card.querySelector('.department-title').textContent;

        if (confirm(`Are you sure you want to delete "${departmentName}"? This action cannot be undone.`)) {
            try {
                // Get CSRF token from form or cookie
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || getCookie("csrftoken");

                const response = await fetch(`/departments/delete/${deptId}/`, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrfToken,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                });

                const data = await response.json();
                console.log('Delete response:', data);

                if (response.ok && data.success) {
                    showNotification(data.message || 'Department deleted successfully! Reloading...', 'success');

                    // Reload page to get fresh data from database
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    showNotification(data.error || "Delete failed.", 'error');
                }
            } catch (error) {
                console.error('Delete error:', error);
                showNotification("Error deleting department.", 'error');
            }
        }
    }

    // Update stats cards
    function updateStats() {
        // Count departments from the DOM
        const allCards = document.querySelectorAll('.department-card');
        const totalCount = allCards.length;

        let activeCount = 0;
        let inactiveCount = 0;

        allCards.forEach(card => {
            const statusBadge = card.querySelector('.department-status');
            if (statusBadge) {
                const status = statusBadge.textContent.trim().toLowerCase();
                if (status === 'active') {
                    activeCount++;
                } else if (status === 'inactive') {
                    inactiveCount++;
                }
            }
        });

        // Update the stats display
        const totalDeptElement = document.querySelector('.stats-grid .stat-card:nth-child(1) .stat-info h3');
        const activeDeptElement = document.querySelector('.stats-grid .stat-card:nth-child(2) .stat-info h3');
        const inactiveDeptElement = document.querySelector('.stats-grid .stat-card:nth-child(3) .stat-info h3');

        if (totalDeptElement) totalDeptElement.textContent = totalCount;
        if (activeDeptElement) activeDeptElement.textContent = activeCount;
        if (inactiveDeptElement) inactiveDeptElement.textContent = inactiveCount;

        console.log('Stats updated:', { total: totalCount, active: activeCount, inactive: inactiveCount });
    }

    // Show empty state
    function showEmptyState() {
        const emptyStateHTML = `
            <div class="empty-state" id="emptyState">
                <i class="fas fa-building"></i>
                <h3>No Departments Found</h3>
                <p>Get started by creating your first department</p>
                <button id="newDepartmentBtnEmpty" class="btn btn-primary">
                    <i class="fas fa-plus"></i> Add Department
                </button>
            </div>
        `;
        departmentsGrid.innerHTML = emptyStateHTML;

        // Re-attach event listener to the new button
        document.getElementById('newDepartmentBtnEmpty').addEventListener('click', openModal);
    }

    // Event delegation for edit and delete buttons
    if (departmentsGrid) {
        departmentsGrid.addEventListener('click', (e) => {
            const card = e.target.closest('.department-card');
            if (!card) return;

            const deptId = card.getAttribute('data-id');
            console.log('Department card clicked:', deptId);

            if (e.target.closest('.edit-btn') || e.target.classList.contains('edit-btn')) {
                e.preventDefault();
                e.stopPropagation();
                setupEditDepartment(card, deptId);
            }

            if (e.target.closest('.delete-btn') || e.target.classList.contains('delete-btn')) {
                e.preventDefault();
                e.stopPropagation();
                deleteDepartment(deptId, card);
            }

            if (e.target.closest('.assign-employees-btn') || e.target.classList.contains('assign-employees-btn')) {
                e.preventDefault();
                e.stopPropagation();
                const deptName = card.querySelector('.department-title').textContent;
                openAssignEmployeesModal(deptId, deptName);
            }

            if (e.target.closest('.view-employees-btn') || e.target.classList.contains('view-employees-btn')) {
                e.preventDefault();
                e.stopPropagation();
                const deptName = card.querySelector('.department-title').textContent;
                openViewEmployeesModal(deptId, deptName);
            }
        });
    }

    // Assign Employees Modal functionality
    const assignEmployeesModal = document.getElementById('assignEmployeesModal');
    const closeAssignModal = document.getElementById('closeAssignModal');
    const cancelAssignBtn = document.getElementById('cancelAssignBtn');
    const assignEmployeesForm = document.getElementById('assignEmployeesForm');
    const assignModalTitle = document.getElementById('assignModalTitle');
    const employeesList = document.getElementById('employeesList');
    const assignDeptId = document.getElementById('assignDeptId');
    const employeeSearchInput = document.getElementById('employeeSearchInput');

    // Store employee data for filtering
    let allEmployeesData = [];
    let assignedEmployeesData = [];

    function openAssignEmployeesModal(deptId, deptName) {
        console.log('Opening assign employees modal for department:', deptId);
        assignModalTitle.textContent = `Assign Employees to ${deptName}`;
        assignDeptId.value = deptId;
        employeesList.innerHTML = '<p>Loading employees...</p>';

        // Clear search input
        if (employeeSearchInput) {
            employeeSearchInput.value = '';
        }

        assignEmployeesModal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Fetch employees
        fetch(`/departments/${deptId}/employees/`)
            .then(response => response.json())
            .then(data => {
                console.log('Employees data:', data);
                // Store employee data for filtering
                allEmployeesData = data.all || [];
                assignedEmployeesData = data.assigned || [];
                renderAssignEmployeesList(allEmployeesData, assignedEmployeesData);
            })
            .catch(error => {
                console.error('Error fetching employees:', error);
                employeesList.innerHTML = '<p class="error">Error loading employees. Please try again.</p>';
            });
    }

    // Render employee list for the Assign Employees modal
    function renderAssignEmployeesList(allEmployees, assignedEmployees, searchTerm = '') {
        const assignedIds = assignedEmployees.map(emp => emp.id);

        // Filter employees based on search term
        let filteredEmployees = allEmployees;
        if (searchTerm && searchTerm.trim() !== '') {
            const searchLower = searchTerm.toLowerCase().trim();
            filteredEmployees = allEmployees.filter(emp => {
                const code = (emp.code || '').toLowerCase();
                const firstname = (emp.firstname || '').toLowerCase();
                const lastname = (emp.lastname || '').toLowerCase();
                const fullName = `${firstname} ${lastname}`.trim();
                return code.includes(searchLower) ||
                       firstname.includes(searchLower) ||
                       lastname.includes(searchLower) ||
                       fullName.includes(searchLower);
            });
        }

        if (filteredEmployees.length === 0) {
            employeesList.innerHTML = '<p>No employees found matching your search.</p>';
            return;
        }

        let html = '';
        filteredEmployees.forEach(emp => {
            const isAssigned = assignedIds.includes(emp.id);
            const checked = isAssigned ? 'checked' : '';
            const currentDept = emp.department_id ? ` (Current: Dept ${emp.department_id})` : '';
            html += `
                <label style="display: flex; align-items: center; padding: 0.5rem; margin-bottom: 0.5rem; cursor: pointer; border-radius: 4px; background: ${isAssigned ? '#e8f5e9' : '#f5f5f5'};">
                    <input type="checkbox" name="employee_ids[]" value="${emp.id}" ${checked} style="margin-right: 0.5rem;">
                    <span>${emp.code} - ${emp.firstname} ${emp.lastname || ''}${currentDept}</span>
                    ${isAssigned ? '<span style="margin-left: auto; color: green; font-size: 0.85rem;">(Already assigned)</span>' : ''}
                </label>
            `;
        });
        employeesList.innerHTML = html;
    }

    // Add search functionality
    if (employeeSearchInput) {
        employeeSearchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value;
            renderAssignEmployeesList(allEmployeesData, assignedEmployeesData, searchTerm);
        });
    }

    function closeAssignModalFunc() {
        assignEmployeesModal.classList.remove('active');
        document.body.style.overflow = 'auto';
        employeesList.innerHTML = '';
        // Clear search and stored data
        if (employeeSearchInput) {
            employeeSearchInput.value = '';
        }
        allEmployeesData = [];
        assignedEmployeesData = [];
    }

    if (closeAssignModal) {
        closeAssignModal.addEventListener('click', closeAssignModalFunc);
    }

    if (cancelAssignBtn) {
        cancelAssignBtn.addEventListener('click', closeAssignModalFunc);
    }

    if (assignEmployeesModal) {
        assignEmployeesModal.addEventListener('click', (e) => {
            if (e.target === assignEmployeesModal) {
                closeAssignModalFunc();
            }
        });
    }

    if (assignEmployeesForm) {
        assignEmployeesForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const deptId = assignDeptId.value;
            const formData = new FormData(assignEmployeesForm);
            const submitBtn = document.getElementById('assignSubmitBtn');

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Assigning...';
            }

            try {
                const csrfToken = assignEmployeesForm.querySelector('[name=csrfmiddlewaretoken]')?.value || getCookie("csrftoken");

                const response = await fetch(`/departments/${deptId}/assign/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: formData
                });

                const data = await response.json();

                if (data.success) {
                    showNotification(data.message, 'success');
                    closeAssignModalFunc();
                    // Reload page to update employee counts
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    showNotification(data.error || 'Error assigning employees', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showNotification('An error occurred while assigning employees', 'error');
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'Assign Selected Employees';
                }
            }
        });
    }

    // View Employees Modal functionality
    const viewEmployeesModal = document.getElementById('viewEmployeesModal');
    const closeViewEmployeesModal = document.getElementById('closeViewEmployeesModal');
    const closeViewEmployeesBtn = document.getElementById('closeViewEmployeesBtn');
    const viewEmployeesContent = document.getElementById('viewEmployeesContent');
    const viewEmployeesModalTitle = document.getElementById('viewEmployeesModalTitle');

    function openViewEmployeesModal(deptId, deptName) {
        console.log('Opening view employees modal for department:', deptId);
        viewEmployeesModalTitle.textContent = `Employees in ${deptName}`;
        viewEmployeesContent.innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: #667eea;"></i>
                <p style="margin-top: 1rem; color: #666;">Loading employees...</p>
            </div>
        `;
        viewEmployeesModal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Fetch employees
        fetch(`/departments/${deptId}/employees/`)
            .then(response => response.json())
            .then(data => {
                console.log('Employees data:', data);
                renderViewEmployeesList(data.assigned || [], data.department_name || deptName);
            })
            .catch(error => {
                console.error('Error fetching employees:', error);
                viewEmployeesContent.innerHTML = `
                    <div style="text-align: center; padding: 2rem;">
                        <i class="fas fa-exclamation-circle" style="font-size: 2rem; color: #f56565;"></i>
                        <p style="margin-top: 1rem; color: #666;">Error loading employees. Please try again.</p>
                    </div>
                `;
            });
    }

    // Render employee list for the View Employees modal
    function renderViewEmployeesList(employees, departmentName) {
        if (employees.length === 0) {
            viewEmployeesContent.innerHTML = `
                <div style="text-align: center; padding: 2rem;">
                    <i class="fas fa-users" style="font-size: 3rem; color: #cbd5e0; margin-bottom: 1rem;"></i>
                    <h3 style="color: #4a5568; margin-bottom: 0.5rem;">No Employees</h3>
                    <p style="color: #718096;">This department has no employees assigned yet.</p>
                </div>
            `;
            return;
        }

        let html = `
            <div style="margin-bottom: 1rem;">
                <p style="color: #666; font-size: 0.875rem; margin-bottom: 1rem;">
                    <strong>Total Employees:</strong> ${employees.length}
                </p>
            </div>
            <div style="max-height: 400px; overflow-y: auto;">
        `;

        employees.forEach((emp, index) => {
            const fullName = `${emp.firstname || ''} ${emp.lastname || ''}`.trim() || 'N/A';
            const email = emp.official_email || emp.email || 'N/A';
            const position = emp.position__name || 'Not assigned';
            const status = emp.status === 1 ? 'Active' : 'Inactive';
            const statusColor = emp.status === 1 ? '#48bb78' : '#cbd5e0';
            const dateHired = emp.date_hired ? new Date(emp.date_hired).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            }) : 'N/A';

            html += `
                <div class="employee-card" style="
                    padding: 1rem;
                    margin-bottom: 0.75rem;
                    background: white;
                    border-radius: 8px;
                    border: 1px solid #e0e0e0;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                ">
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <div style="
                            width: 48px;
                            height: 48px;
                            border-radius: 50%;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: white;
                            font-weight: bold;
                            font-size: 1.2rem;
                            flex-shrink: 0;
                        ">
                            ${(emp.firstname || 'E')[0].toUpperCase()}
                        </div>
                        <div style="flex: 1; min-width: 0;">
                            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
                                <h4 style="margin: 0; color: #2d3748; font-size: 1rem; font-weight: 600;">
                                    ${fullName}
                                </h4>
                                <span style="
                                    padding: 0.125rem 0.5rem;
                                    border-radius: 12px;
                                    font-size: 0.75rem;
                                    font-weight: 500;
                                    background: ${statusColor}20;
                                    color: ${statusColor};
                                ">${status}</span>
                            </div>
                            <div style="display: flex; flex-wrap: wrap; gap: 1rem; font-size: 0.875rem; color: #666;">
                                <div style="display: flex; align-items: center; gap: 0.25rem;">
                                    <i class="fas fa-id-badge" style="color: #667eea;"></i>
                                    <span><strong>ID:</strong> ${emp.code || 'N/A'}</span>
                                </div>
                                <div style="display: flex; align-items: center; gap: 0.25rem;">
                                    <i class="fas fa-briefcase" style="color: #667eea;"></i>
                                    <span><strong>Position:</strong> ${position}</span>
                                </div>
                                <div style="display: flex; align-items: center; gap: 0.25rem;">
                                    <i class="fas fa-envelope" style="color: #667eea;"></i>
                                    <span><strong>Email:</strong> ${email}</span>
                                </div>
                                <div style="display: flex; align-items: center; gap: 0.25rem;">
                                    <i class="fas fa-calendar-alt" style="color: #667eea;"></i>
                                    <span><strong>Hired:</strong> ${dateHired}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        html += `</div>`;
        viewEmployeesContent.innerHTML = html;
    }

    function closeViewEmployeesModalFunc() {
        viewEmployeesModal.classList.remove('active');
        document.body.style.overflow = 'auto';
        viewEmployeesContent.innerHTML = '';
    }

    if (closeViewEmployeesModal) {
        closeViewEmployeesModal.addEventListener('click', closeViewEmployeesModalFunc);
    }

    if (closeViewEmployeesBtn) {
        closeViewEmployeesBtn.addEventListener('click', closeViewEmployeesModalFunc);
    }

    if (viewEmployeesModal) {
        viewEmployeesModal.addEventListener('click', (e) => {
            if (e.target === viewEmployeesModal) {
                closeViewEmployeesModalFunc();
            }
        });
    }

    console.log('Departments script initialized successfully');
});

// Utility functions
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

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
}

// Notification function
function showNotification(message, type = 'info') {
    // Remove any existing notifications
    const existingNotifications = document.querySelectorAll('.custom-notification');
    existingNotifications.forEach(notification => {
        notification.remove();
    });

    // Create new notification
    const notification = document.createElement('div');
    notification.className = `custom-notification ${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${getNotificationIcon(type)}"></i>
            <span>${message}</span>
        </div>
        <button class="notification-close">
            <i class="fas fa-times"></i>
        </button>
    `;

    document.body.appendChild(notification);

    // Show notification
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);

    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);

    // Close button event
    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.classList.remove('show');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    });
}

function getNotificationIcon(type) {
    const icons = {
        'success': 'check-circle',
        'error': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    return icons[type] || 'info-circle';
}

// Add CSS for notifications
const notificationStyles = `
    .custom-notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: var(--bg-card, #ffffff);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #667eea;
        z-index: 10001;
        transform: translateX(400px);
        transition: transform 0.3s ease;
        max-width: 400px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
    }
    .custom-notification.show {
        transform: translateX(0);
    }
    .custom-notification.success {
        border-left-color: #48bb78;
    }
    .custom-notification.error {
        border-left-color: #f56565;
    }
    .custom-notification.warning {
        border-left-color: #f59e0b;
    }
    .custom-notification.info {
        border-left-color: #667eea;
    }
    .notification-content {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        flex: 1;
    }
    .notification-close {
        background: none;
        border: none;
        color: var(--text-light, #718096);
        cursor: pointer;
        padding: 0.25rem;
        border-radius: 4px;
        transition: all 0.3s ease;
    }
    .notification-close:hover {
        background: var(--bg-light, #f8fafc);
        color: var(--text-dark, #2d3748);
    }
`;

// Inject styles
if (!document.querySelector('#notification-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'notification-styles';
    styleSheet.textContent = notificationStyles;
    document.head.appendChild(styleSheet);
}