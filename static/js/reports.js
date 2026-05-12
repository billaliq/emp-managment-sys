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

    // Theme toggle functionality - Now handled by appearance.js for persistence
    // This is kept for backward compatibility but appearance.js takes precedence

    // Generate Report Modal
    const generateReportBtn = document.getElementById('generateReportBtn');
    const generateReportModal = document.getElementById('generateReportModal');
    const closeModal = document.getElementById('closeModal');
    const cancelBtn = document.getElementById('cancelBtn');

    if (generateReportBtn && generateReportModal) {
        generateReportBtn.addEventListener('click', () => {
            generateReportModal.classList.add('active');
        });
    }

    if (closeModal && generateReportModal) {
        closeModal.addEventListener('click', () => {
            generateReportModal.classList.remove('active');
        });
    }

    if (cancelBtn && generateReportModal) {
        cancelBtn.addEventListener('click', () => {
            generateReportModal.classList.remove('active');
        });
    }

    // Close modal when clicking outside
    if (generateReportModal) {
        generateReportModal.addEventListener('click', (e) => {
            if (e.target === generateReportModal) {
                generateReportModal.classList.remove('active');
            }
        });
    }

    // Show/hide custom date range
    const dateRangeSelect = document.getElementById('dateRange');
    const customDateRange = document.getElementById('customDateRange');

    if (dateRangeSelect && customDateRange) {
        dateRangeSelect.addEventListener('change', () => {
            if (dateRangeSelect.value === 'custom') {
                customDateRange.style.display = 'grid';
            } else {
                customDateRange.style.display = 'none';
            }
        });
    }

    // Form submission is handled in the inline script in reports.html
    // Removed duplicate handler to prevent double submission

    // Real-time updates for processing reports
    function checkProcessingReports() {
        const processingBadges = document.querySelectorAll('.badge.processing');
        if (processingBadges.length > 0) {
            // Reload page to update status
            setTimeout(() => {
                window.location.reload();
            }, 3000);
        }
    }

    // Check every 5 seconds
    setInterval(checkProcessingReports, 5000);
});

// Global functions for template actions
function downloadReport(reportId) {
    window.location.href = `/reports/download/${reportId}/`;
}

function viewReport(reportId) {
    window.location.href = `/reports/view/${reportId}/`;
}

async function deleteReport(reportId) {
    if (!confirm('Are you sure you want to delete this report?')) {
        return;
    }

    try {
        const response = await fetch(`/reports/delete/${reportId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json'
            }
        });

        // Check if response is JSON before parsing
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Non-JSON response:', text.substring(0, 200));
            throw new Error('Server returned an invalid response. Please try again.');
        }

        if (!response.ok) {
            // Try to get error message from JSON response
            try {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            } catch (e) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        }

        const data = await response.json();

        if (data.success) {
            alert('Report deleted successfully');
            window.location.reload();
        } else {
            alert('Error: ' + (data.message || 'Failed to delete report'));
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('Error deleting report: ' + error.message);
    }
}

function generateFromTemplate(reportType) {
    const reportTypeSelect = document.getElementById('reportType');
    if (reportTypeSelect) {
        reportTypeSelect.value = reportType;
        document.getElementById('generateReportModal').classList.add('active');
    }
}

function viewTemplate(templateId) {
    // Implement template view functionality
    alert('Template view functionality coming soon!');
}

function refreshReports() {
    window.location.reload();
}

// Utility function to get CSRF token
function getCSRFToken() {
    const name = 'csrftoken';
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