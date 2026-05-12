// Global Appearance Settings - Applied to all pages
(function() {
    'use strict';

    // Update theme toggle icon based on current theme
    function updateThemeToggleIcon() {
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            const htmlElement = document.documentElement;
            const isDark = htmlElement.getAttribute('data-theme') === 'dark';
            themeToggle.innerHTML = isDark
                ? '<i class="fas fa-sun"></i>'
                : '<i class="fas fa-moon"></i>';
        }
    }

    // Apply appearance settings from system settings
    function applyAppearanceSettings() {
        const htmlElement = document.documentElement;
        const bodyElement = document.body;

        // Prioritize localStorage over data attributes to ensure persistence
        // Check localStorage first, then fall back to data attributes
        const darkModeFromStorage = localStorage.getItem('dark_mode');
        const darkMode = darkModeFromStorage !== null
            ? darkModeFromStorage === 'true'
            : (htmlElement.getAttribute('data-dark-mode') === 'true');

        // Prioritize localStorage for theme as well
        const themeFromStorage = localStorage.getItem('theme');
        const theme = themeFromStorage !== null
            ? themeFromStorage
            : (htmlElement.getAttribute('data-theme-color') || 'default');

        const fontSize = localStorage.getItem('font_size') ||
                        htmlElement.getAttribute('data-font-size') || 'medium';
        const sidebarWidth = localStorage.getItem('sidebar_width') ||
                           htmlElement.getAttribute('data-sidebar-width') || 'normal';

        // Apply dark mode - prioritize localStorage
        if (darkMode) {
            htmlElement.setAttribute('data-theme', 'dark');
            // Ensure localStorage is set
            if (darkModeFromStorage !== 'true') {
                localStorage.setItem('dark_mode', 'true');
            }
        } else {
            htmlElement.removeAttribute('data-theme');
            // Ensure localStorage is set
            if (darkModeFromStorage !== 'false') {
                localStorage.setItem('dark_mode', 'false');
            }
        }

        // Update theme toggle icon based on current theme
        updateThemeToggleIcon();

        // Apply theme colors - always apply from localStorage if available
        applyThemeColors(theme);
        // Ensure localStorage is set for theme
        if (themeFromStorage !== theme) {
            localStorage.setItem('theme', theme);
        }

        // Apply font size
        if (fontSize === 'small') {
            bodyElement.style.fontSize = '14px';
        } else if (fontSize === 'large') {
            bodyElement.style.fontSize = '18px';
        } else {
            bodyElement.style.fontSize = '16px';
        }
        htmlElement.setAttribute('data-font-size', fontSize);

        // Apply sidebar width
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
            sidebar.classList.remove('compact', 'normal', 'wide');
            sidebar.classList.add(sidebarWidth);
        }
        htmlElement.setAttribute('data-sidebar-width', sidebarWidth);
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

        // Method 1: Set CSS variables on :root element (inline styles)
        root.style.setProperty('--primary-color', primaryColor);
        root.style.setProperty('--secondary-color', secondaryColor);
        root.style.setProperty('--gradient-primary',
            `linear-gradient(135deg, ${primaryColor} 0%, ${secondaryColor} 100%)`);

        // Method 2: Also inject a style tag to ensure it overrides CSS
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

        root.setAttribute('data-theme-color', theme);

        // Force a reflow to ensure styles are applied
        void root.offsetHeight;

        // Also update any elements that might have hardcoded gradients
        updateThemeGradients(primaryColor, secondaryColor);

        // Dispatch custom event for charts to update
        document.dispatchEvent(new CustomEvent('themeChanged'));
    }

    // Update theme gradients in specific elements
    function updateThemeGradients(primaryColor, secondaryColor) {
        // Update splash screen gradient
        const splashScreen = document.querySelector('.splash-screen');
        if (splashScreen) {
            splashScreen.style.background = `linear-gradient(135deg, ${primaryColor} 0%, ${secondaryColor} 100%)`;
        }

        // Update any buttons or elements with gradient-primary class
        const gradientElements = document.querySelectorAll('.gradient-primary, [style*="gradient-primary"]');
        gradientElements.forEach(el => {
            if (el.style.background && el.style.background.includes('gradient')) {
                el.style.background = `linear-gradient(135deg, ${primaryColor} 0%, ${secondaryColor} 100%)`;
            }
        });
    }

    // Load settings from server on page load
    async function loadSettingsFromServer() {
        try {
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
            const response = await fetch('/api/settings/get/', {
                headers: {
                    'X-CSRFToken': csrftoken
                }
            });

            if (response.ok) {
                const data = await response.json();

                if (data.success && data.settings) {
                    const settings = data.settings;
                    const htmlElement = document.documentElement;
                    const bodyElement = document.body;

                    // Apply appearance settings
                    if (settings.appearance) {
                        // Dark mode - only update if localStorage doesn't have a value
                        // This ensures user's manual toggle persists
                        const currentDarkMode = localStorage.getItem('dark_mode');
                        if (currentDarkMode === null) {
                            // Only apply server settings if no local preference exists
                            if (settings.appearance.dark_mode) {
                                htmlElement.setAttribute('data-theme', 'dark');
                                localStorage.setItem('dark_mode', 'true');
                            } else {
                                htmlElement.removeAttribute('data-theme');
                                localStorage.setItem('dark_mode', 'false');
                            }
                        } else {
                            // Respect localStorage preference
                            if (currentDarkMode === 'true') {
                                htmlElement.setAttribute('data-theme', 'dark');
                            } else {
                                htmlElement.removeAttribute('data-theme');
                            }
                        }
                        // Update toggle icon
                        updateThemeToggleIcon();

                        // Theme - only update if localStorage doesn't have a value
                        // This ensures user's manual selection persists
                        const currentTheme = localStorage.getItem('theme');
                        if (currentTheme === null) {
                            // Only apply server settings if no local preference exists
                            if (settings.appearance.theme) {
                                applyThemeColors(settings.appearance.theme);
                                localStorage.setItem('theme', settings.appearance.theme);
                            }
                        } else {
                            // Respect localStorage preference
                            applyThemeColors(currentTheme);
                        }

                        // Font size
                        if (settings.appearance.font_size) {
                            const fontSize = settings.appearance.font_size;
                            if (fontSize === 'small') {
                                bodyElement.style.fontSize = '14px';
                            } else if (fontSize === 'large') {
                                bodyElement.style.fontSize = '18px';
                            } else {
                                bodyElement.style.fontSize = '16px';
                            }
                            htmlElement.setAttribute('data-font-size', fontSize);
                            localStorage.setItem('font_size', fontSize);
                        }

                        // Sidebar width
                        if (settings.appearance.sidebar_width) {
                            const sidebar = document.getElementById('sidebar');
                            if (sidebar) {
                                sidebar.classList.remove('compact', 'normal', 'wide');
                                sidebar.classList.add(settings.appearance.sidebar_width);
                            }
                            htmlElement.setAttribute('data-sidebar-width', settings.appearance.sidebar_width);
                            localStorage.setItem('sidebar_width', settings.appearance.sidebar_width);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error loading settings:', error);
            // Fallback to localStorage if server request fails
            applyAppearanceSettings();
        }
    }

    // Initialize theme toggle handler
    function initializeThemeToggle() {
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            // Check if already initialized (avoid duplicate listeners)
            if (themeToggle.dataset.initialized === 'true') {
                return;
            }

            // Mark as initialized
            themeToggle.dataset.initialized = 'true';

            // Add click event listener
            themeToggle.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();

                const htmlElement = document.documentElement;
                const currentTheme = htmlElement.getAttribute('data-theme');

                if (currentTheme === 'dark') {
                    // Switch to light mode
                    htmlElement.removeAttribute('data-theme');
                    localStorage.setItem('dark_mode', 'false');
                    updateThemeToggleIcon();
                } else {
                    // Switch to dark mode
                    htmlElement.setAttribute('data-theme', 'dark');
                    localStorage.setItem('dark_mode', 'true');
                    updateThemeToggleIcon();
                }

                // Trigger storage event to sync across tabs
                window.dispatchEvent(new StorageEvent('storage', {
                    key: 'dark_mode',
                    newValue: currentTheme === 'dark' ? 'false' : 'true'
                }));
            });
        }
    }

    // Initialize theme toggle on page load
    function initializeTheme() {
        // Apply settings immediately from localStorage first (for instant dark mode)
        applyAppearanceSettings();
        // Then initialize toggle handler
        initializeThemeToggle();
    }

    // Apply theme and dark mode immediately on script load (before DOM ready) to prevent flash
    (function applyThemeImmediately() {
        const darkMode = localStorage.getItem('dark_mode') === 'true';
        const theme = localStorage.getItem('theme') || 'default';

        // Apply dark mode
        if (darkMode) {
            document.documentElement.setAttribute('data-theme', 'dark');
        }

        // Apply theme colors immediately using the same function
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

        root.setAttribute('data-theme-color', theme);

        // Force a reflow to ensure styles are applied
        void root.offsetHeight;
    })();

    // Initialize on page load
    function initializeOnLoad() {
        initializeTheme();
        // Reapply theme after CSS loads to ensure it overrides CSS :root
        setTimeout(function() {
            const theme = localStorage.getItem('theme') || 'default';
            if (theme) {
                applyThemeColors(theme);
            }
        }, 50);
        // Also reapply after a longer delay to catch any late-loading CSS
        setTimeout(function() {
            const theme = localStorage.getItem('theme') || 'default';
            if (theme) {
                applyThemeColors(theme);
            }
        }, 300);
        // Load server settings after local settings are applied
        loadSettingsFromServer();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeOnLoad);
    } else {
        initializeOnLoad();
    }

    // Listen for storage events to sync across tabs and handle same-tab changes
    window.addEventListener('storage', function(e) {
        if (e.key === 'dark_mode' || e.key === 'theme' || e.key === 'font_size' || e.key === 'sidebar_width') {
            applyAppearanceSettings();
            updateThemeToggleIcon();
            // If theme changed, apply it immediately
            if (e.key === 'theme' && e.newValue) {
                applyThemeColors(e.newValue);
            }
        }
    });

    // Also listen for custom events dispatched from same tab (settings page)
    window.addEventListener('themeChanged', function(e) {
        if (e.detail && e.detail.theme) {
            applyThemeColors(e.detail.theme);
            applyAppearanceSettings();
        }
    });

    // Expose function for settings page to trigger refresh
    window.refreshAppearance = function() {
        loadSettingsFromServer();
        applyAppearanceSettings();
        updateThemeToggleIcon();
    };
})();

