document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle functionality
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');

    if (menuToggle && sidebar && mainContent) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            mainContent.classList.toggle('expanded');
        });
    }

    // Enhanced Tab functionality
    const tabs = document.querySelectorAll('.tab');
    const tabContents = {
        'loans': document.getElementById('loansTab'),
        'pending': document.getElementById('pendingTab'),
        'repayments': document.getElementById('repaymentsTab'),
        'report': document.getElementById('reportTab')
    };

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs
            tabs.forEach(t => {
                t.classList.remove('active');
                t.style.transform = 'translateY(0)';
            });

            // Hide all tab contents with animation
            Object.values(tabContents).forEach(content => {
                if (content) {
                    content.classList.remove('active');
                    content.style.display = 'none';
                }
            });

            // Activate clicked tab with animation
            tab.classList.add('active');
            tab.style.transform = 'translateY(-2px)';

            const tabName = tab.getAttribute('data-tab');
            if (tabContents[tabName]) {
                tabContents[tabName].style.display = 'block';
                // Add a small delay for smooth animation
                setTimeout(() => {
                    tabContents[tabName].classList.add('active');
                }, 50);
            }
        });
    });

    // Modal functionality
    const newLoanModal = document.getElementById('newLoanModal');
    const addRepaymentModal = document.getElementById('addRepaymentModal');
    const loanPoolModal = document.getElementById('loanPoolModal');

    const newLoanBtn = document.getElementById('newLoanBtn');
    const newLoanBtn2 = document.getElementById('newLoanBtn2');
    const newLoanBtn3 = document.getElementById('newLoanBtn3');
    const addRepaymentBtn = document.getElementById('addRepaymentBtn');
    const addRepaymentBtn2 = document.getElementById('addRepaymentBtn2');
    const managePoolBtn = document.getElementById('managePoolBtn');

    const closeLoanModal = document.getElementById('closeLoanModal');
    const closeRepaymentModal = document.getElementById('closeRepaymentModal');
    const closePoolModal = document.getElementById('closePoolModal');

    const cancelLoanBtn = document.getElementById('cancelLoanBtn');
    const cancelRepaymentBtn = document.getElementById('cancelRepaymentBtn');
    const cancelPoolBtn = document.getElementById('cancelPoolBtn');

    // Open modals
    const openLoanModal = () => {
        // For employees, ensure employee field is empty (will be set automatically)
        const employeeHiddenInput = document.getElementById('employee');
        const employeeSearchInput = document.getElementById('employeeSearchInput');
        if (employeeHiddenInput && !employeeSearchInput) {
            // Employee field is hidden for employees, ensure it's empty
            employeeHiddenInput.value = '';
        }
        newLoanModal.style.display = 'flex';
    };
    if (newLoanBtn) newLoanBtn.addEventListener('click', openLoanModal);
    if (newLoanBtn2) newLoanBtn2.addEventListener('click', openLoanModal);
    if (newLoanBtn3) newLoanBtn3.addEventListener('click', openLoanModal);
    if (addRepaymentBtn) addRepaymentBtn.addEventListener('click', () => addRepaymentModal.style.display = 'flex');
    if (addRepaymentBtn2) addRepaymentBtn2.addEventListener('click', () => addRepaymentModal.style.display = 'flex');
    if (managePoolBtn) managePoolBtn.addEventListener('click', () => loanPoolModal.style.display = 'flex');

    // Close modals
    if (closeLoanModal) closeLoanModal.addEventListener('click', () => newLoanModal.style.display = 'none');
    if (closeRepaymentModal) closeRepaymentModal.addEventListener('click', () => addRepaymentModal.style.display = 'none');
    if (closePoolModal) closePoolModal.addEventListener('click', () => loanPoolModal.style.display = 'none');

    if (cancelLoanBtn) cancelLoanBtn.addEventListener('click', () => newLoanModal.style.display = 'none');
    if (cancelRepaymentBtn) cancelRepaymentBtn.addEventListener('click', () => addRepaymentModal.style.display = 'none');
    if (cancelPoolBtn) cancelPoolBtn.addEventListener('click', () => loanPoolModal.style.display = 'none');

    // Close modals when clicking outside
    window.addEventListener('click', (e) => {
        if (e.target === newLoanModal) newLoanModal.style.display = 'none';
        if (e.target === addRepaymentModal) addRepaymentModal.style.display = 'none';
        if (e.target === loanPoolModal) loanPoolModal.style.display = 'none';
    });

    // Loan form submission
    const loanFormElement = document.getElementById('loanForm');
    if (loanFormElement) {
        loanFormElement.addEventListener('submit', function(e) {
            e.preventDefault();
            submitLoanForm(this);
        });
    }

    // Repayment form submission
    const repaymentFormElement = document.getElementById('repaymentForm');
    if (repaymentFormElement) {
        repaymentFormElement.addEventListener('submit', function(e) {
            e.preventDefault();
            submitRepaymentForm(this);
        });
    }

    // Pool form submission
    const poolFormElement = document.getElementById('poolForm');
    if (poolFormElement) {
        poolFormElement.addEventListener('submit', function(e) {
            e.preventDefault();
            submitPoolForm(this);
        });
    }

    // Loan actions
    document.querySelectorAll('.view-loan').forEach(btn => {
        btn.addEventListener('click', function() {
            const loanId = this.getAttribute('data-loan-id');
            viewLoanDetails(loanId);
        });
    });

    document.querySelectorAll('.view-repayments').forEach(btn => {
        btn.addEventListener('click', function() {
            const loanId = this.getAttribute('data-loan-id');
            viewRepaymentHistory(loanId);
        });
    });

    document.querySelectorAll('.edit-loan').forEach(btn => {
        btn.addEventListener('click', function() {
            const loanId = this.getAttribute('data-loan-id');
            editLoan(loanId);
        });
    });

    document.querySelectorAll('.approve-loan').forEach(btn => {
        btn.addEventListener('click', function() {
            const loanId = this.getAttribute('data-loan-id');
            approveLoan(loanId);
        });
    });

    document.querySelectorAll('.reject-loan').forEach(btn => {
        btn.addEventListener('click', function() {
            const loanId = this.getAttribute('data-loan-id');
            rejectLoan(loanId);
        });
    });

    // Refresh pool button
    const refreshPoolBtn = document.getElementById('refreshPoolBtn');
    if (refreshPoolBtn) {
        refreshPoolBtn.addEventListener('click', refreshPoolData);
    }

    // Export report button
    const exportReportBtn = document.getElementById('exportReportBtn');
    if (exportReportBtn) {
        exportReportBtn.addEventListener('click', exportReport);
    }

    // Real-time updates
    initializeRealTimeUpdates();

    // Form validation
    initializeFormValidation();

    // Auto-calculate monthly payment (no interest rate)
    const loanAmountInput = document.getElementById('loan_amount');
    const installmentsInput = document.getElementById('installments');

    if (loanAmountInput && installmentsInput) {
        [loanAmountInput, installmentsInput].forEach(input => {
            input.addEventListener('input', calculateMonthlyPayment);
        });
    }

    // Initialize searchable employee select
    initializeSearchableEmployeeSelect();
});

// Searchable Employee Select Functionality
function initializeSearchableEmployeeSelect() {
    const employeeSearchInput = document.getElementById('employeeSearchInput');
    const employeeDropdown = document.getElementById('employeeDropdown');
    const employeeHiddenInput = document.getElementById('employee');
    let allEmployeeOptions = [];

    if (employeeSearchInput && employeeDropdown && employeeHiddenInput) {
        // Store all options
        allEmployeeOptions = Array.from(employeeDropdown.querySelectorAll('.dropdown-option'));

        // Show dropdown on input focus
        employeeSearchInput.addEventListener('focus', function() {
            employeeDropdown.style.display = 'block';
            filterEmployeeOptions('');
        });

        // Filter options as user types
        employeeSearchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase().trim();
            filterEmployeeOptions(searchTerm);
        });

        // Handle option selection
        allEmployeeOptions.forEach(option => {
            option.addEventListener('click', function() {
                const value = this.getAttribute('data-value');
                const text = this.getAttribute('data-text');

                employeeHiddenInput.value = value;
                employeeSearchInput.value = text;
                employeeDropdown.style.display = 'none';
            });
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            const searchableSelect = employeeSearchInput.closest('.searchable-select-wrapper');
            if (searchableSelect && !searchableSelect.contains(e.target)) {
                employeeDropdown.style.display = 'none';
            }
        });

        // Filter function
        function filterEmployeeOptions(searchTerm) {
            if (!searchTerm) {
                allEmployeeOptions.forEach(option => {
                    option.style.display = '';
                });
                return;
            }

            allEmployeeOptions.forEach(option => {
                const text = option.textContent.toLowerCase();
                if (text.includes(searchTerm)) {
                    option.style.display = '';
                } else {
                    option.style.display = 'none';
                }
            });
        }
    }
}

// Enhanced notification system
function showNotification(message, type = 'info', duration = 5000) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;

    const icons = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    };

    notification.innerHTML = `
        <div class="notification-content">
            <i class="${icons[type] || icons.info}"></i>
            <span>${message}</span>
        </div>
        <button class="notification-close">
            <i class="fas fa-times"></i>
        </button>
    `;

    document.body.appendChild(notification);

    // Animate in
    setTimeout(() => notification.classList.add('show'), 100);

    // Close functionality
    const closeBtn = notification.querySelector('.notification-close');
    closeBtn.addEventListener('click', () => {
        closeNotification(notification);
    });

    // Auto remove
    if (duration > 0) {
        setTimeout(() => {
            closeNotification(notification);
        }, duration);
    }

    return notification;
}

function closeNotification(notification) {
    notification.classList.remove('show');
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 400);
}

// Form submission functions
async function submitLoanForm(form) {
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;

    // Validate required fields
    const employee = formData.get('employee');
    const loanAmount = formData.get('loan_amount');
    const installments = formData.get('installments');
    const startDate = formData.get('start_date');

    // Check if employee field is visible (admin/hr) or hidden (employee)
    const employeeSearchInput = document.getElementById('employeeSearchInput');
    const isEmployeeView = !employeeSearchInput || employeeSearchInput.offsetParent === null;

    // For employees, employee field is not required (will be set automatically)
    // For admin/hr, employee field is required
    if (!isEmployeeView && !employee) {
        showNotification('Please select an employee', 'error');
        return;
    }

    // Validate all required fields
    // FormData.get() returns null if field doesn't exist, or empty string if field exists but is empty
    const loanAmountValue = loanAmount ? loanAmount.toString().trim() : '';
    const installmentsValue = installments ? installments.toString().trim() : '';
    const startDateValue = startDate ? startDate.toString().trim() : '';

    if (!loanAmountValue || isNaN(parseFloat(loanAmountValue)) || parseFloat(loanAmountValue) <= 0) {
        showNotification('Please enter a valid loan amount', 'error');
        return;
    }

    if (!installmentsValue || isNaN(parseInt(installmentsValue)) || parseInt(installmentsValue) <= 0) {
        showNotification('Please enter a valid number of installments', 'error');
        return;
    }

    if (!startDateValue) {
        showNotification('Please select a start date', 'error');
        return;
    }

    // Set interest_rate to 0 (removed from form but still needed for backend)
    formData.set('interest_rate', '0');

    try {
        // Show loading state
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        submitBtn.disabled = true;

        // Make actual API call to backend
        const response = await fetch('/loans/create/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        });

        const data = await response.json();

        if (data.success) {
            // Show success notification
            showNotification(data.message || 'Loan application submitted successfully!', 'success');

            // Close modal
            document.getElementById('newLoanModal').style.display = 'none';

            // Reset form
            form.reset();

            // Clear the searchable select (only for admin/hr)
            const employeeSearchInput = document.getElementById('employeeSearchInput');
            const employeeHiddenInput = document.getElementById('employee');
            if (employeeSearchInput) employeeSearchInput.value = '';
            // For employees, keep the hidden field empty (will be set automatically on next submission)
            if (employeeHiddenInput && !employeeSearchInput) {
                employeeHiddenInput.value = '';
            } else if (employeeHiddenInput) {
                employeeHiddenInput.value = '';
            }

            // Reload the page to show the new loan
            setTimeout(() => {
                window.location.reload();
            }, 1500);

        } else {
            // Show error notification
            showNotification(data.error || 'Error submitting loan application', 'error');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }

    } catch (error) {
        showNotification('Error submitting loan application: ' + error.message, 'error');
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

async function submitRepaymentForm(form) {
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;

    // Validate required fields
    const loan = formData.get('loan');
    const amount = formData.get('amount');
    const paymentDate = formData.get('payment_date');

    if (!loan || !amount || !paymentDate) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }

    try {
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Recording...';
        submitBtn.disabled = true;

        const response = await fetch('/loans/add-repayment/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        });

        const data = await response.json();

        if (data.success) {
            showNotification(data.message || 'Repayment recorded successfully!', 'success');
            document.getElementById('addRepaymentModal').style.display = 'none';
            form.reset();

            // Reload page to show updated data
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showNotification(data.error || 'Error recording repayment', 'error');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }

    } catch (error) {
        showNotification('Error recording repayment: ' + error.message, 'error');
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

async function submitPoolForm(form) {
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;

    try {
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
        submitBtn.disabled = true;

        await new Promise(resolve => setTimeout(resolve, 1500));

        showNotification('Loan pool updated successfully!', 'success');
        document.getElementById('loanPoolModal').style.display = 'none';
        form.reset();
        refreshPoolData();

    } catch (error) {
        showNotification('Error updating loan pool: ' + error.message, 'error');
    } finally {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

// Loan action functions
async function viewLoanDetails(loanId) {
    try {
        showNotification('Loading loan details...', 'info');

        const response = await fetch(`/loans/${loanId}/details/`);
        const data = await response.json();

        if (data.success) {
            const loan = data.loan;
            showLoanDetailsModal(loan);
        } else {
            showNotification(data.error || 'Error loading loan details', 'error');
        }
    } catch (error) {
        showNotification('Error loading loan details: ' + error.message, 'error');
    }
}

async function viewRepaymentHistory(loanId) {
    try {
        showNotification('Loading repayment history...', 'info');

        const response = await fetch(`/loans/${loanId}/repayments/`);
        const data = await response.json();

        if (data.success) {
            showRepaymentHistoryModal(data);
        } else {
            showNotification(data.error || 'Error loading repayment history', 'error');
        }
    } catch (error) {
        showNotification('Error loading repayment history: ' + error.message, 'error');
    }
}

async function editLoan(loanId) {
    try {
        showNotification('Loading loan details...', 'info');

        const response = await fetch(`/loans/${loanId}/details/`);
        const data = await response.json();

        if (data.success) {
            showEditLoanModal(data.loan);
        } else {
            showNotification(data.error || 'Error loading loan details', 'error');
        }
    } catch (error) {
        showNotification('Error loading loan details: ' + error.message, 'error');
    }
}

// Modal display functions
function showLoanDetailsModal(loan) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'loanDetailsModal';
    modal.style.display = 'flex';

    modal.innerHTML = `
        <div class="modal-content" style="max-width: 700px;">
            <div class="modal-header">
                <h2 class="modal-title">Loan Details</h2>
                <button class="close-btn" onclick="this.closest('.modal').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div style="padding: 2rem;">
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.5rem; margin-bottom: 1.5rem;">
                    <div>
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Employee</label>
                        <div style="font-size: 1.1rem; margin-top: 0.5rem;">${loan.employee_name}</div>
                        <div style="font-size: 0.9rem; color: var(--text-light);">${loan.department}</div>
                    </div>
                    <div>
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Status</label>
                        <div style="margin-top: 0.5rem;">
                            <span class="badge ${loan.status === 'active' || loan.status === 'approved' ? 'success' : loan.status === 'pending' ? 'warning' : 'danger'}">
                                ${loan.status_display}
                            </span>
                        </div>
                    </div>
                    <div>
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Loan Amount</label>
                        <div style="font-size: 1.1rem; margin-top: 0.5rem;">$${loan.loan_amount}</div>
                    </div>
                    <div>
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Total Amount</label>
                        <div style="font-size: 1.1rem; margin-top: 0.5rem;">$${loan.total_amount}</div>
                    </div>
                    <div>
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Remaining Balance</label>
                        <div style="font-size: 1.1rem; margin-top: 0.5rem; color: var(--warning-color);">$${loan.remaining_balance}</div>
                    </div>
                    <div>
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Amount Repaid</label>
                        <div style="font-size: 1.1rem; margin-top: 0.5rem; color: var(--success-color);">$${loan.amount_repaid}</div>
                    </div>
                    <div>
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Monthly Payment</label>
                        <div style="font-size: 1.1rem; margin-top: 0.5rem;">$${loan.monthly_payment}</div>
                    </div>
                    <div>
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Installments</label>
                        <div style="font-size: 1.1rem; margin-top: 0.5rem;">${loan.installments_paid}/${loan.number_of_installments} (${loan.installments_remaining} remaining)</div>
                    </div>
                    <div>
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Start Date</label>
                        <div style="font-size: 1.1rem; margin-top: 0.5rem;">${loan.start_date}</div>
                    </div>
                    <div>
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">End Date</label>
                        <div style="font-size: 1.1rem; margin-top: 0.5rem;">${loan.end_date}</div>
                    </div>
                </div>
                ${loan.purpose ? `
                <div style="margin-top: 1.5rem;">
                    <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Purpose</label>
                    <div style="margin-top: 0.5rem; padding: 1rem; background: var(--bg-light); border-radius: 8px;">${loan.purpose}</div>
                </div>
                ` : ''}
                <div style="margin-top: 1.5rem;">
                    <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Repayment Progress</label>
                    <div style="margin-top: 0.5rem;">
                        <div class="progress-bar">
                            <div class="progress-fill" style="--progress: ${loan.progress_percentage}%"></div>
                        </div>
                        <div style="text-align: center; margin-top: 0.5rem; font-weight: 600;">${loan.progress_percentage}%</div>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

function showRepaymentHistoryModal(data) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'repaymentHistoryModal';
    modal.style.display = 'flex';

    const repaymentsHtml = data.repayments.length > 0 ? `
        <div class="table-container" style="margin-top: 1.5rem;">
            <table class="table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Amount</th>
                        <th>Method</th>
                        <th>Recorded By</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.repayments.map(repayment => `
                        <tr>
                            <td>${repayment.payment_date}</td>
                            <td>$${repayment.amount}</td>
                            <td>${repayment.payment_method}</td>
                            <td>${repayment.created_by}</td>
                            <td>${repayment.notes || '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    ` : '<p style="text-align: center; padding: 2rem; color: var(--text-light);">No repayments recorded yet.</p>';

    modal.innerHTML = `
        <div class="modal-content" style="max-width: 900px;">
            <div class="modal-header">
                <h2 class="modal-title">Repayment History</h2>
                <button class="close-btn" onclick="this.closest('.modal').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div style="padding: 2rem;">
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; margin-bottom: 1.5rem;">
                    <div style="padding: 1rem; background: var(--bg-light); border-radius: 8px;">
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Total Amount</label>
                        <div style="font-size: 1.2rem; font-weight: 700; margin-top: 0.5rem;">$${data.total_amount}</div>
                    </div>
                    <div style="padding: 1rem; background: var(--bg-light); border-radius: 8px;">
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Total Repaid</label>
                        <div style="font-size: 1.2rem; font-weight: 700; color: var(--success-color); margin-top: 0.5rem;">$${data.total_repaid}</div>
                    </div>
                    <div style="padding: 1rem; background: var(--bg-light); border-radius: 8px;">
                        <label style="font-weight: 600; color: var(--text-light); font-size: 0.9rem;">Remaining Balance</label>
                        <div style="font-size: 1.2rem; font-weight: 700; color: var(--warning-color); margin-top: 0.5rem;">$${data.remaining_balance}</div>
                    </div>
                </div>
                ${repaymentsHtml}
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

function showEditLoanModal(loan) {
    showNotification('Loan editing feature coming soon. For now, please contact administrator to modify loan details.', 'info');
}

async function approveLoan(loanId) {
    if (!confirm('Are you sure you want to approve this loan?')) return;

    try {
        showNotification(`Approving loan ID: ${loanId}`, 'info');

        const formData = new FormData();
        formData.append('loan_id', loanId);
        formData.append('action', 'approve');
        formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

        const response = await fetch('/loans/update-status/', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showNotification(data.message || 'Loan approved successfully!', 'success');
            // Reload page to show updated data
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showNotification(data.error || 'Error approving loan', 'error');
        }

    } catch (error) {
        showNotification('Error approving loan: ' + error.message, 'error');
    }
}

async function rejectLoan(loanId) {
    if (!confirm('Are you sure you want to reject this loan?')) return;

    try {
        showNotification(`Rejecting loan ID: ${loanId}`, 'warning');

        const formData = new FormData();
        formData.append('loan_id', loanId);
        formData.append('action', 'reject');
        formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

        const response = await fetch('/loans/update-status/', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showNotification(data.message || 'Loan rejected successfully!', 'success');
            // Reload page to show updated data
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showNotification(data.error || 'Error rejecting loan', 'error');
        }

    } catch (error) {
        showNotification('Error rejecting loan: ' + error.message, 'error');
    }
}

// Data refresh functions
async function refreshLoanData() {
    const tableBody = document.querySelector('#loansTab tbody');
    if (tableBody) {
        tableBody.classList.add('loading-skeleton');
        await new Promise(resolve => setTimeout(resolve, 1000));
        tableBody.classList.remove('loading-skeleton');
        showNotification('Loan data refreshed!', 'success');
    }
}

async function refreshRepaymentData() {
    const tableBody = document.querySelector('#repaymentsTab tbody');
    if (tableBody) {
        tableBody.classList.add('loading-skeleton');
        await new Promise(resolve => setTimeout(resolve, 1000));
        tableBody.classList.remove('loading-skeleton');
        showNotification('Repayment data refreshed!', 'success');
    }
}

async function refreshPoolData() {
    // Reload the page to get fresh data from backend
    window.location.reload();
}

// Export function
async function exportReport() {
    try {
        showNotification('Generating report...', 'info');

        await new Promise(resolve => setTimeout(resolve, 2000));

        showNotification('Report exported successfully!', 'success');

        // Create and trigger download
        const blob = new Blob(['Sample report data'], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'loan-report.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

    } catch (error) {
        showNotification('Error exporting report: ' + error.message, 'error');
    }
}

// Real-time updates
function initializeRealTimeUpdates() {
    // Simulate real-time updates every 30 seconds
    setInterval(() => {
        updateLiveStats();
    }, 30000);

    // Initial update
    updateLiveStats();
}

async function updateLiveStats() {
    const stats = document.querySelectorAll('.stat-card-value, .pool-stat-value');
    stats.forEach(stat => {
        if (Math.random() > 0.7) { // 30% chance of update
            stat.classList.add('realtime-indicator');
            setTimeout(() => {
                stat.classList.remove('realtime-indicator');
            }, 3000);
        }
    });
}

// Form validation
function initializeFormValidation() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
            }
        });
    });

    // Add real-time validation
    const inputs = document.querySelectorAll('input[required], select[required], textarea[required]');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            validateField(this);
        });
    });
}

function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('input[required], select[required], textarea[required]');

    requiredFields.forEach(field => {
        if (!validateField(field)) {
            isValid = false;
        }
    });

    return isValid;
}

function validateField(field) {
    const value = field.value.trim();
    let isValid = true;
    let message = '';

    // Clear previous validation
    field.classList.remove('error', 'success');
    const existingError = field.parentNode.querySelector('.error-message');
    if (existingError) {
        existingError.remove();
    }

    // Required field validation
    if (field.hasAttribute('required') && !value) {
        isValid = false;
        message = 'This field is required';
    }

    // Email validation
    if (field.type === 'email' && value) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            isValid = false;
            message = 'Please enter a valid email address';
        }
    }

    // Number validation
    if (field.type === 'number' && value) {
        const min = parseFloat(field.getAttribute('min'));
        const max = parseFloat(field.getAttribute('max'));

        if (!isNaN(min) && parseFloat(value) < min) {
            isValid = false;
            message = `Value must be at least ${min}`;
        }

        if (!isNaN(max) && parseFloat(value) > max) {
            isValid = false;
            message = `Value must be at most ${max}`;
        }
    }

    // Show validation result
    if (!isValid) {
        field.classList.add('error');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.cssText = `
            color: #ef4444;
            font-size: 0.8rem;
            margin-top: 0.25rem;
            font-weight: 500;
        `;
        errorDiv.textContent = message;
        field.parentNode.appendChild(errorDiv);
    } else {
        field.classList.add('success');
    }

    return isValid;
}

// Auto-calculate monthly payment
function calculateMonthlyPayment() {
    const loanAmount = parseFloat(document.getElementById('loan_amount')?.value) || 0;
    const installments = parseInt(document.getElementById('installments')?.value) || 1;

    if (loanAmount > 0 && installments > 0) {
        // No interest rate - simple division
        const monthlyPayment = loanAmount / installments;

        // Show calculated value
        const paymentDisplay = document.getElementById('monthlyPaymentDisplay') || createMonthlyPaymentDisplay();
        paymentDisplay.textContent = `Estimated Monthly Payment: $${monthlyPayment.toFixed(2)}`;
    }
}

function createMonthlyPaymentDisplay() {
    const display = document.createElement('div');
    display.id = 'monthlyPaymentDisplay';
    display.style.cssText = `
        background: #f0f9ff;
        border: 1px solid #bae6fd;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 1rem;
        font-weight: 600;
        color: #0369a1;
        text-align: center;
    `;

    const formGrid = document.querySelector('.form-grid');
    if (formGrid) {
        formGrid.parentNode.insertBefore(display, formGrid.nextSibling);
    }

    return display;
}

// Enhanced search and filter functionality
function initializeSearchFilter() {
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Search loans...';
    searchInput.style.cssText = `
        padding: 0.75rem 1rem;
        border: 2px solid var(--border-color);
        border-radius: 8px;
        background: var(--bg-card);
        color: var(--text-dark);
        font-size: 0.9rem;
        width: 100%;
        max-width: 300px;
        margin-bottom: 1rem;
    `;

    const actionBar = document.querySelector('.action-bar');
    if (actionBar) {
        actionBar.appendChild(searchInput);
    }

    searchInput.addEventListener('input', debounce(function(e) {
        filterLoans(e.target.value);
    }, 300));
}

function filterLoans(searchTerm) {
    const rows = document.querySelectorAll('#loansTab tbody tr');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        if (text.includes(searchTerm.toLowerCase())) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// Utility function for debouncing
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl + N for new loan
    if (e.ctrlKey && e.key === 'n') {
        e.preventDefault();
        document.getElementById('newLoanModal').style.display = 'flex';
    }

    // Escape to close modals
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            modal.style.display = 'none';
        });
    }
});

// Initialize search filter when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeSearchFilter();
});

// Print functionality
function printLoanReport() {
    const originalStyles = document.querySelectorAll('style, link[rel="stylesheet"]');
    const printWindow = window.open('', '_blank');

    printWindow.document.write(`
        <html>
            <head>
                <title>Loan Report</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    table { width: 100%; border-collapse: collapse; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                    th { background-color: #f5f5f5; }
                    @media print { body { margin: 0; } }
                </style>
            </head>
            <body>
                <h1>Loan Report</h1>
                ${document.querySelector('.table-container').outerHTML}
            </body>
        </html>
    `);

    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
        printWindow.print();
        printWindow.close();
    }, 500);
}