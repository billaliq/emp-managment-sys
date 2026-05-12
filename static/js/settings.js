// Settings Page - Real-time Updates
(function() {
    'use strict';

    // Get CSRF token
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

    const csrftoken = getCSRFToken();
    const htmlElement = document.documentElement;

    // Real-time settings update function
    async function updateSetting(section, key, value, element) {
        try {
            const response = await fetch('/api/settings/update/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify({
                    section: section,
                    key: key,
                    value: value
                })
            });

            const data = await response.json();

            if (data.success) {
                // Show success indicator
                showSuccessIndicator(element);

                // Apply visual changes instantly for appearance settings
                if (section === 'appearance') {
                    applyAppearanceChange(key, value);
                }

                return true;
            } else {
                showErrorIndicator(element, data.message);
                return false;
            }
        } catch (error) {
            console.error('Error updating setting:', error);
            showErrorIndicator(element, error.message);
            return false;
        }
    }

    // Apply appearance changes instantly and globally
    function applyAppearanceChange(key, value) {
        if (key === 'dark_mode') {
            const isDark = value === true || value === 'true' || value === '1' || value === 'on';
            if (isDark) {
                htmlElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('dark_mode', 'true');
                const themeToggle = document.getElementById('themeToggle');
                if (themeToggle) {
                    themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
                }
            } else {
                htmlElement.removeAttribute('data-theme');
                localStorage.setItem('dark_mode', 'false');
                const themeToggle = document.getElementById('themeToggle');
                if (themeToggle) {
                    themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
                }
            }
            // Trigger refresh on other tabs
            window.dispatchEvent(new Event('storage'));
        } else if (key === 'theme') {
            // Apply theme colors immediately
            htmlElement.setAttribute('data-theme-color', value);
            localStorage.setItem('theme', value);
            applyThemeColors(value);

            // Trigger custom event for same-tab updates
            window.dispatchEvent(new CustomEvent('themeChanged', {
                detail: { theme: value }
            }));

            // Trigger storage event to sync across tabs
            // Note: StorageEvent only works across tabs, not same tab
            // So we use CustomEvent for same-tab updates
            try {
                window.dispatchEvent(new StorageEvent('storage', {
                    key: 'theme',
                    newValue: value,
                    oldValue: localStorage.getItem('theme')
                }));
            } catch (e) {
                // StorageEvent might not work in all browsers for same-tab
                // CustomEvent handles this case
            }
        } else if (key === 'font_size') {
            htmlElement.setAttribute('data-font-size', value);
            localStorage.setItem('font_size', value);
            document.body.style.fontSize = value === 'small' ? '14px' : value === 'large' ? '18px' : '16px';
            window.dispatchEvent(new Event('storage'));
        } else if (key === 'sidebar_width') {
            htmlElement.setAttribute('data-sidebar-width', value);
            localStorage.setItem('sidebar_width', value);
            const sidebar = document.getElementById('sidebar');
            const mainContent = document.getElementById('mainContent');
            if (sidebar) {
                sidebar.classList.remove('sidebar-compact', 'sidebar-normal', 'sidebar-wide');
                sidebar.classList.add('sidebar-' + value);
            }
            if (mainContent) {
                mainContent.classList.remove('sidebar-compact', 'sidebar-normal', 'sidebar-wide');
                mainContent.classList.add('sidebar-' + value);
            }
            window.dispatchEvent(new Event('storage'));
        }

        // Refresh appearance globally if function exists
        if (typeof window.refreshAppearance === 'function') {
            window.refreshAppearance();
        }
    }

    // Apply theme colors
    function applyThemeColors(theme) {
        const root = document.documentElement;
        let primaryColor, secondaryColor;

        switch(theme) {
            case 'indigo':
                primaryColor = '#4f46e5';
                secondaryColor = '#7c3aed';
                break;
            case 'emerald':
                primaryColor = '#059669';
                secondaryColor = '#0d9488';
                break;
            case 'crimson':
                primaryColor = '#dc2626';
                secondaryColor = '#ea580c';
                break;
            default:
                primaryColor = '#667eea';
                secondaryColor = '#764ba2';
        }

        // Set CSS variables on :root
        root.style.setProperty('--primary-color', primaryColor);
        root.style.setProperty('--secondary-color', secondaryColor);
        root.style.setProperty('--gradient-primary',
            `linear-gradient(135deg, ${primaryColor} 0%, ${secondaryColor} 100%)`);

        // Also inject a style tag to ensure it overrides CSS
        let themeStyle = document.getElementById('dynamic-theme-styles');
        if (!themeStyle) {
            themeStyle = document.createElement('style');
            themeStyle.id = 'dynamic-theme-styles';
            document.head.appendChild(themeStyle);
        }
        themeStyle.textContent = `
            :root {
                --primary-color: ${primaryColor} !important;
                --secondary-color: ${secondaryColor} !important;
                --gradient-primary: linear-gradient(135deg, ${primaryColor} 0%, ${secondaryColor} 100%) !important;
            }
        `;

        // Force a reflow to ensure styles are applied
        void root.offsetHeight;

        // Update splash screen if it exists
        const splashScreen = document.querySelector('.splash-screen');
        if (splashScreen) {
            splashScreen.style.background = `linear-gradient(135deg, ${primaryColor} 0%, ${secondaryColor} 100%)`;
        }

        // Dispatch custom event for charts to update
        document.dispatchEvent(new CustomEvent('themeChanged'));
    }

    // Show success indicator
    function showSuccessIndicator(element) {
        const parent = element.closest('.form-group');
        if (parent) {
            const statusIcon = parent.querySelector('.fa-check-circle');
            const statusText = parent.querySelector('.save-status');
            if (statusIcon) {
                statusIcon.style.display = 'inline-block';
                setTimeout(() => {
                    statusIcon.style.display = 'none';
                }, 2000);
            }
            if (statusText) {
                statusText.textContent = 'Saved!';
                setTimeout(() => {
                    statusText.textContent = statusText.getAttribute('data-original-text') || 'Changes save automatically';
                }, 2000);
            }
        }
    }

    // Show error indicator
    function showErrorIndicator(element, message) {
        const parent = element.closest('.form-group');
        if (parent) {
            const statusText = parent.querySelector('.save-status');
            if (statusText) {
                const originalText = statusText.textContent;
                statusText.setAttribute('data-original-text', originalText);
                statusText.textContent = 'Error: ' + message;
                statusText.style.color = '#dc2626';
                setTimeout(() => {
                    statusText.textContent = originalText;
                    statusText.style.color = '';
                }, 3000);
            }
        }
    }

    // Initialize settings page
    function initializeSettings() {
        // Settings navigation
        const settingsNavItems = document.querySelectorAll('.settings-nav-item');
        const settingsSections = document.querySelectorAll('.settings-section');

        settingsNavItems.forEach(item => {
            item.addEventListener('click', () => {
                const target = item.getAttribute('data-target');

                settingsNavItems.forEach(navItem => navItem.classList.remove('active'));
                settingsSections.forEach(section => section.classList.remove('active'));

                item.classList.add('active');
                const targetSection = document.getElementById(target);
                if (targetSection) {
                    targetSection.classList.add('active');
                }
            });
        });

        // Theme options selection
        const themeOptions = document.querySelectorAll('.theme-option[data-realtime="true"]');
        themeOptions.forEach(option => {
            option.addEventListener('click', () => {
                const section = option.getAttribute('data-section');
                const key = option.getAttribute('data-key');
                const value = option.getAttribute('data-value');

                themeOptions.forEach(opt => opt.classList.remove('active'));
                option.classList.add('active');

                updateSetting(section, key, value, option);
            });
        });

        // Real-time input handlers
        const realtimeInputs = document.querySelectorAll('.setting-input[data-realtime="true"]');
        realtimeInputs.forEach(input => {
            const section = input.getAttribute('data-section');
            const key = input.getAttribute('data-key');

            if (input.type === 'checkbox') {
                input.addEventListener('change', function() {
                    updateSetting(section, key, this.checked, this);
                });
            } else if (input.tagName === 'SELECT') {
                input.addEventListener('change', function() {
                    updateSetting(section, key, this.value, this);
                });
            } else if (input.type === 'text' || input.type === 'number') {
                let timeout;
                input.addEventListener('input', function() {
                    clearTimeout(timeout);
                    timeout = setTimeout(() => {
                        updateSetting(section, key, this.value, this);
                    }, 500); // Debounce for text inputs
                });
            }
        });

        // Dark mode toggle
        const darkModeToggle = document.getElementById('darkModeToggle');
        if (darkModeToggle) {
            // Set initial state
            if (darkModeToggle.checked) {
                htmlElement.setAttribute('data-theme', 'dark');
            }
        }

        // Load current settings and apply them
        loadAndApplySettings();
    }

    // Load and apply current settings
    async function loadAndApplySettings() {
        try {
            const response = await fetch('/api/settings/get/', {
                headers: {
                    'X-CSRFToken': csrftoken
                }
            });

            const data = await response.json();

            if (data.success && data.settings) {
                const settings = data.settings;

                // Apply appearance settings
                if (settings.appearance) {
                    if (settings.appearance.dark_mode) {
                        htmlElement.setAttribute('data-theme', 'dark');
                    }
                    if (settings.appearance.theme) {
                        applyThemeColors(settings.appearance.theme);
                    }
                    if (settings.appearance.font_size) {
                        document.body.style.fontSize = settings.appearance.font_size === 'small' ? '14px' :
                                                       settings.appearance.font_size === 'large' ? '18px' : '16px';
                    }
                    if (settings.appearance.sidebar_width) {
                        const sidebar = document.getElementById('sidebar');
                        const mainContent = document.getElementById('mainContent');
                        if (sidebar) {
                            sidebar.classList.remove('sidebar-compact', 'sidebar-normal', 'sidebar-wide');
                            sidebar.classList.add('sidebar-' + settings.appearance.sidebar_width);
                        }
                        if (mainContent) {
                            mainContent.classList.remove('sidebar-compact', 'sidebar-normal', 'sidebar-wide');
                            mainContent.classList.add('sidebar-' + settings.appearance.sidebar_width);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error loading settings:', error);
        }
    }

    // Backup and Restore functions (global scope)
    window.createBackup = function() {
        if (confirm('This will create a backup of all system data. Continue?')) {
            alert('Backup functionality will be implemented. This feature is coming soon.');
        }
    };

    window.restoreBackup = function() {
        if (confirm('This will restore data from a backup. All current data will be replaced. Continue?')) {
            alert('Restore functionality will be implemented. This feature is coming soon.');
        }
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeSettings);
    } else {
        initializeSettings();
    }
})();
