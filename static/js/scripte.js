// JavaScript for Dashboard Functionality
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');
    const menuToggle = document.getElementById('menuToggle');
    const themeToggle = document.getElementById('themeToggle');
    const notificationBtn = document.getElementById('notificationBtn');
    const notificationDropdown = document.getElementById('notificationDropdown');
    const userProfile = document.getElementById('userProfile');
    const userDropdown = document.getElementById('userDropdown');
    // const searchInput = document.getElementById('searchInput');
    const searchResults = document.getElementById('searchResults');
    const addEmployeeModal = document.getElementById('addEmployeeModal');
    const closeModal = document.getElementById('closeModal');
    const cancelBtn = document.getElementById('cancelBtn');
    const employeeForm = document.getElementById('employeeForm');
    const loading = document.getElementById('loading');
    const employeesMenu = document.getElementById('employeesMenu');
    const employeesSubmenu = document.getElementById('employeesSubmenu');
    const attendanceMenu = document.getElementById('attendanceMenu');
    const attendanceSubmenu = document.getElementById('attendanceSubmenu');
    const deviceMenu = document.getElementById('deviceMenu');
    const deviceSubmenu = document.getElementById('deviceSubmenu');
    const splashScreen = document.getElementById('splashScreen');

    // Splash Screen - Now handled by splash.js for consistency
    // Keeping this for backward compatibility but splash.js takes precedence
    if (splashScreen && !window.splashScreenHandled) {
        splashScreen.style.display = 'flex';
        setTimeout(function() {
            splashScreen.style.opacity = '0';
            setTimeout(function() {
                splashScreen.style.display = 'none';
            }, 400);
        }, 2000); // Display time: 2 seconds
    }

    // Sidebar Toggle
    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('active');
        });
    }

    // Submenu Toggles
    if (employeesMenu && employeesSubmenu) {
        employeesMenu.addEventListener('click', function(e) {
            e.preventDefault();
            employeesMenu.classList.toggle('expanded');
            employeesSubmenu.classList.toggle('expanded');
        });
    }

    if (attendanceMenu && attendanceSubmenu) {
        attendanceMenu.addEventListener('click', function(e) {
            e.preventDefault();
            attendanceMenu.classList.toggle('expanded');
            attendanceSubmenu.classList.toggle('expanded');
        });
    }

    if (deviceMenu && deviceSubmenu) {
        deviceMenu.addEventListener('click', function(e) {
            e.preventDefault();
            deviceMenu.classList.toggle('expanded');
            deviceSubmenu.classList.toggle('expanded');
        });
    }

    // Logout Confirmation
    window.confirmLogout = function() {
        // Create a more elegant confirmation dialog
        const confirmed = confirm('Are you sure you want to logout? You will need to sign in again to access the system.');
        if (confirmed) {
            // Add a loading state
            const logoutLinks = document.querySelectorAll('.logout-link, .logout-item');
            logoutLinks.forEach(link => {
                link.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Logging out...';
                link.style.pointerEvents = 'none';
            });
        }
        return confirmed;
    };

    // Keyboard shortcut for logout (Ctrl+Q)
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'q') {
            e.preventDefault();
            if (confirmLogout()) {
                window.location.href = '/logout/';
            }
        }
    });

    // Theme Toggle - Now handled by appearance.js for persistence
    // This is kept for backward compatibility but appearance.js takes precedence

    // User Dropdown Toggle
    if (userProfile && userDropdown) {
        userProfile.addEventListener('click', function(e) {
            e.stopPropagation();
            userDropdown.classList.toggle('active');
            if (notificationDropdown) {
                notificationDropdown.classList.remove('active');
            }
        });
    }

    // Close dropdowns when clicking outside (but not on the buttons or dropdowns themselves)
    document.addEventListener('click', function(e) {
        // Check if click is outside notification wrapper and dropdown
        if (notificationBtn && notificationDropdown) {
            const notificationWrapper = notificationBtn.closest('.notification-wrapper');
            if (notificationWrapper) {
                if (!notificationWrapper.contains(e.target) && !notificationDropdown.contains(e.target)) {
                    notificationDropdown.classList.remove('active');
                }
            } else {
                // Fallback if wrapper not found
                if (!notificationBtn.contains(e.target) && !notificationDropdown.contains(e.target)) {
                    notificationDropdown.classList.remove('active');
                }
            }
        }
        // Check if click is outside user profile and dropdown
        if (userProfile && userDropdown) {
            if (!userProfile.contains(e.target) && !userDropdown.contains(e.target)) {
                userDropdown.classList.remove('active');
            }
        }
    });

    // // Search Functionality
    // if (searchInput && searchResults) {
    //     searchInput.addEventListener('focus', function() {
    //         searchResults.classList.add('active');
    //     });

    //     searchInput.addEventListener('input', function() {
    //         if (this.value.length > 0) {
    //             searchResults.classList.add('active');
    //         } else {
    //             searchResults.classList.remove('active');
    //         }
    //     });
    // }

    // Add Employee Modal
    if (closeModal && addEmployeeModal) {
        closeModal.addEventListener('click', function() {
            addEmployeeModal.classList.remove('active');
        });
    }

    if (cancelBtn && addEmployeeModal) {
        cancelBtn.addEventListener('click', function() {
            addEmployeeModal.classList.remove('active');
        });
    }

    // Employee Form Submission
    if (employeeForm && loading && addEmployeeModal) {
        employeeForm.addEventListener('submit', function(e) {
            e.preventDefault();
            loading.classList.add('active');
            setTimeout(function() {
                loading.classList.remove('active');
                addEmployeeModal.classList.remove('active');
                alert('Employee added successfully!');
                employeeForm.reset();
            }, 1500);
        });
    }

    // ==============================
    // Charts Initialization (Dynamic)
    // ==============================

    // Helper function to get theme colors from CSS variables
    function getThemeColors() {
        const root = getComputedStyle(document.documentElement);
        const primaryColor = root.getPropertyValue('--primary-color').trim() || '#667eea';
        const secondaryColor = root.getPropertyValue('--secondary-color').trim() || '#764ba2';
        const accentColor = root.getPropertyValue('--accent-color').trim() || '#f093fb';

        // Convert hex to rgb for rgba
        function hexToRgb(hex) {
            const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
            return result ? {
                r: parseInt(result[1], 16),
                g: parseInt(result[2], 16),
                b: parseInt(result[3], 16)
            } : null;
        }

        const primaryRgb = hexToRgb(primaryColor) || { r: 102, g: 126, b: 234 };
        const secondaryRgb = hexToRgb(secondaryColor) || { r: 118, g: 75, b: 162 };
        const accentRgb = hexToRgb(accentColor) || { r: 240, g: 147, b: 251 };

        return {
            primary: primaryColor,
            secondary: secondaryColor,
            accent: accentColor,
            primaryRgba: `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, 0.7)`,
            primaryRgb: `rgb(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b})`,
            secondaryRgba: `rgba(${secondaryRgb.r}, ${secondaryRgb.g}, ${secondaryRgb.b}, 0.7)`,
            secondaryRgb: `rgb(${secondaryRgb.r}, ${secondaryRgb.g}, ${secondaryRgb.b})`,
            accentRgba: `rgba(${accentRgb.r}, ${accentRgb.g}, ${accentRgb.b}, 0.7)`,
            accentRgb: `rgb(${accentRgb.r}, ${accentRgb.g}, ${accentRgb.b})`
        };
    }

    // Store chart instances globally for download/expand functionality
    let departmentChartInstance = null;
    let genderChartInstance = null;

    // Function to initialize department chart
    function initDepartmentChart() {
        // Check if data exists and is valid
        if (typeof departmentStats === 'undefined' || !departmentStats || !Array.isArray(departmentStats) || departmentStats.length === 0) {
            console.log('Department stats not available for chart');
            return;
        }

        const departmentCtx = document.getElementById('departmentChart');
        if (!departmentCtx) {
            console.log('Department chart canvas not found');
            return;
        }

        // Destroy existing chart if it exists
        if (departmentChartInstance) {
            departmentChartInstance.destroy();
            departmentChartInstance = null;
        }

        try {
            const themeColors = getThemeColors();
            const departmentLabels = departmentStats.map(item => item.name);
            const departmentCounts = departmentStats.map(item => item.employee_count);

            departmentChartInstance = new Chart(departmentCtx, {
                type: 'bar',
                data: {
                    labels: departmentLabels,
                    datasets: [{
                        label: 'Number of Employees',
                        data: departmentCounts,
                        backgroundColor: themeColors.primaryRgba,
                        borderColor: themeColors.primaryRgb,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: { y: { beginAtZero: true } }
                }
            });
            console.log('Department chart initialized successfully');
        } catch (error) {
            console.error('Error creating department chart:', error);
        }
    }

    // Initialize charts after everything is ready
    function initializeCharts() {
        // Check if Chart.js is available
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js not loaded, retrying...');
            setTimeout(initializeCharts, 200);
            return;
        }

        // Initialize department chart
        if (typeof departmentStats !== 'undefined' && departmentStats && Array.isArray(departmentStats) && departmentStats.length > 0) {
            try {
                initDepartmentChart();
            } catch (error) {
                console.error('Error initializing department chart:', error);
            }
        } else {
            console.log('Department stats not available or empty:', typeof departmentStats, departmentStats);
        }

        // Initialize gender chart
        if (typeof genderStats !== 'undefined' && genderStats && Array.isArray(genderStats) && genderStats.length > 0) {
            try {
                initGenderChart();
            } catch (error) {
                console.error('Error initializing gender chart:', error);
            }
        } else {
            console.log('Gender stats not available or empty:', typeof genderStats, genderStats);
        }
    }

    // Wait for data and Chart.js to be available
    // The data is defined in a script tag at the end of body, so we need to wait
    function tryInitializeCharts() {
        // Check if Chart.js is loaded
        if (typeof Chart === 'undefined') {
            setTimeout(tryInitializeCharts, 100);
            return;
        }

        // Check if data variables exist (they're defined in the template)
        if (typeof departmentStats === 'undefined' || typeof genderStats === 'undefined') {
            // Data not ready yet, try again
            setTimeout(tryInitializeCharts, 100);
            return;
        }

        // Everything is ready, initialize charts after a short delay for theme
        setTimeout(initializeCharts, 150);
    }

    // Start trying to initialize after DOM is ready
    // Use window load to ensure all scripts are loaded
    if (document.readyState === 'loading') {
        window.addEventListener('load', function() {
            setTimeout(tryInitializeCharts, 100);
        });
    } else {
        setTimeout(tryInitializeCharts, 100);
    }

    // Download button functionality
    const downloadBtn = document.getElementById('downloadDepartmentChart');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function() {
            downloadDepartmentChart();
        });
    }

    // Expand button functionality
    const expandBtn = document.getElementById('expandDepartmentChart');
    if (expandBtn) {
        expandBtn.addEventListener('click', function() {
            expandDepartmentChart();
        });
    }

    // Download chart as image
    function downloadDepartmentChart() {
        if (!departmentChartInstance) {
            alert('Chart not available');
            return;
        }

        const url = departmentChartInstance.toBase64Image();
        const link = document.createElement('a');
        link.download = `employee-distribution-by-department-${new Date().toISOString().split('T')[0]}.png`;
        link.href = url;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // Expand chart in fullscreen modal
    function expandDepartmentChart() {
        if (!departmentChartInstance) {
            alert('Chart not available');
            return;
        }

        // Create modal
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.id = 'chartExpandModal';
        modal.style.display = 'flex';
        modal.style.alignItems = 'center';
        modal.style.justifyContent = 'center';
        modal.style.zIndex = '10000';

        // Create modal content
        const modalContent = document.createElement('div');
        modalContent.className = 'modal-content';
        modalContent.style.maxWidth = '90%';
        modalContent.style.maxHeight = '90%';
        modalContent.style.width = '1200px';

        modalContent.innerHTML = `
            <div class="modal-header">
                <h2 class="modal-title">Employee Distribution by Department</h2>
                <button class="close-btn" onclick="document.getElementById('chartExpandModal').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div style="padding: 2rem; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                <div style="width: 100%; height: 600px; position: relative; display: flex; align-items: center; justify-content: center;">
                    <canvas id="expandedDepartmentChart"></canvas>
                </div>
                <div style="margin-top: 1.5rem;">
                    <button class="btn btn-primary" onclick="downloadExpandedChart()">
                        <i class="fas fa-download"></i> Download Chart
                    </button>
                </div>
            </div>
        `;

        modal.appendChild(modalContent);
        document.body.appendChild(modal);

        // Create expanded chart
        setTimeout(() => {
            const expandedCtx = document.getElementById('expandedDepartmentChart');
            if (expandedCtx && typeof departmentStats !== 'undefined') {
                const departmentLabels = departmentStats.map(item => item.name);
                const departmentCounts = departmentStats.map(item => item.employee_count);

                const themeColors = getThemeColors();
                const expandedChart = new Chart(expandedCtx, {
                    type: 'bar',
                    data: {
                        labels: departmentLabels,
                        datasets: [{
                            label: 'Number of Employees',
                            data: departmentCounts,
                            backgroundColor: themeColors.primaryRgba,
                            borderColor: themeColors.primaryRgb,
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: { beginAtZero: true },
                            x: { ticks: { font: { size: 14 } } }
                        },
                        plugins: {
                            legend: { display: true, labels: { font: { size: 14 } } },
                            title: { display: true, text: 'Employee Distribution by Department', font: { size: 18 } }
                        }
                    }
                });

                // Store expanded chart for download
                window.expandedDepartmentChart = expandedChart;
            }
        }, 100);

        // Close modal when clicking outside
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                modal.remove();
                if (window.expandedDepartmentChart) {
                    window.expandedDepartmentChart.destroy();
                    window.expandedDepartmentChart = null;
                }
            }
        });
    }

    // Download expanded chart
    window.downloadExpandedChart = function() {
        if (!window.expandedDepartmentChart) {
            alert('Chart not available');
            return;
        }

        const url = window.expandedDepartmentChart.toBase64Image();
        const link = document.createElement('a');
        link.download = `employee-distribution-by-department-${new Date().toISOString().split('T')[0]}.png`;
        link.href = url;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    // Function to initialize gender chart
    function initGenderChart() {
        // Check if data exists and is valid
        if (typeof genderStats === 'undefined' || !genderStats || !Array.isArray(genderStats) || genderStats.length === 0) {
            console.log('Gender stats not available for chart');
            return;
        }

        const genderCtx = document.getElementById('genderChart');
        if (!genderCtx) {
            console.log('Gender chart canvas not found');
            return;
        }

        // Destroy existing chart if it exists
        if (genderChartInstance) {
            genderChartInstance.destroy();
            genderChartInstance = null;
        }

        try {
            const themeColors = getThemeColors();
            const genderLabels = genderStats.map(item => item.gender || "Not Specified");
            const genderCounts = genderStats.map(item => item.count);

            genderChartInstance = new Chart(genderCtx, {
                type: 'doughnut',
                data: {
                    labels: genderLabels,
                    datasets: [{
                        data: genderCounts,
                        backgroundColor: [
                            themeColors.primaryRgba,
                            themeColors.accentRgba,
                            themeColors.secondaryRgba
                        ],
                        borderColor: [
                            themeColors.primaryRgb,
                            themeColors.accentRgb,
                            themeColors.secondaryRgb
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom' } }
                }
            });
            console.log('Gender chart initialized successfully');
        } catch (error) {
            console.error('Error creating gender chart:', error);
        }
    }

    // Listen for theme changes and update charts
    window.addEventListener('storage', function(e) {
        if (e.key === 'theme') {
            setTimeout(function() {
                if (typeof departmentStats !== 'undefined' && departmentStats.length > 0) {
                    initDepartmentChart();
                }
                if (typeof genderStats !== 'undefined' && genderStats.length > 0) {
                    initGenderChart();
                }
            }, 200);
        }
    });

    // Also listen for theme changes via custom event (for same-tab changes)
    document.addEventListener('themeChanged', function() {
        setTimeout(function() {
            if (typeof departmentStats !== 'undefined' && departmentStats.length > 0) {
                initDepartmentChart();
            }
            if (typeof genderStats !== 'undefined' && genderStats.length > 0) {
                initGenderChart();
            }
        }, 200);
    });

    // Animate elements on scroll
    const animateOnScroll = function() {
        const elements = document.querySelectorAll('.fade-in-up');
        elements.forEach(element => {
            const elementPosition = element.getBoundingClientRect().top;
            const screenPosition = window.innerHeight / 1.3;
            if (elementPosition < screenPosition) {
                element.style.opacity = 1;
                element.style.transform = 'translateY(0)';
            }
        });
    };

    // Initial check on load
    animateOnScroll();
    window.addEventListener('scroll', animateOnScroll);

    // ==============================
    // Chart Download Functionality
    // ==============================
    function downloadChart(chart, filename) {
        const link = document.createElement('a');
        link.href = chart.toBase64Image();
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // Attach download buttons to all charts after a delay to ensure charts are initialized
    setTimeout(() => {
        document.querySelectorAll('.chart-container').forEach(container => {
            const canvas = container.querySelector('canvas');
            if (!canvas) return;

            const chartInstance = Chart.getChart(canvas);
            const downloadBtn = container.querySelector('.fa-download')?.parentElement;

            if (downloadBtn && chartInstance) {
                downloadBtn.addEventListener('click', () => {
                    downloadChart(chartInstance, `${canvas.id}.png`);
                });
            }
        });
    }, 1000);
});
