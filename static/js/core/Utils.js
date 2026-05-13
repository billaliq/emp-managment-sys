/**
 * Utils.js — Shared utility functions (MVC Core)
 * Centralises helpers that were previously duplicated across every JS file.
 */

/**
 * Read a browser cookie by name.
 * Used primarily to retrieve the Django CSRF token.
 * @param {string} name
 * @returns {string|null}
 */
export function getCookie(name) {
    if (!document.cookie) return null;
    const cookies = document.cookie.split(';');
    for (const cookie of cookies) {
        const trimmed = cookie.trim();
        if (trimmed.startsWith(name + '=')) {
            return decodeURIComponent(trimmed.substring(name.length + 1));
        }
    }
    return null;
}

/**
 * Get the Django CSRF token from cookie or a hidden form input.
 * @returns {string}
 */
export function getCsrfToken() {
    // Prefer cookie
    const fromCookie = getCookie('csrftoken');
    if (fromCookie) return fromCookie;
    // Fallback: look for hidden input in any form on the page
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
}

/**
 * Format an ISO date string or Date object into a human-readable locale string.
 * @param {string|Date} dateStr
 * @returns {string}
 */
export function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    try {
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return String(dateStr);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    } catch {
        return String(dateStr);
    }
}

/**
 * Debounce a function call.
 * @param {Function} fn
 * @param {number} delay  milliseconds
 * @returns {Function}
 */
export function debounce(fn, delay = 300) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * Escape HTML special characters to prevent XSS when building innerHTML strings.
 * @param {any} value
 * @returns {string}
 */
export function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * Capitalise the first letter of a string.
 * @param {string} str
 * @returns {string}
 */
export function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Convert a hex colour string to an rgba() string.
 * @param {string} hex   e.g. '#667eea'
 * @param {number} alpha e.g. 0.7
 * @returns {string}     e.g. 'rgba(102, 126, 234, 0.7)'
 */
export function hexToRgba(hex, alpha = 1) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (!result) return `rgba(0,0,0,${alpha})`;
    const r = parseInt(result[1], 16);
    const g = parseInt(result[2], 16);
    const b = parseInt(result[3], 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * Read CSS custom property values from :root.
 * @param {string} variable  e.g. '--primary-color'
 * @returns {string}
 */
export function getCssVar(variable) {
    return getComputedStyle(document.documentElement)
        .getPropertyValue(variable)
        .trim();
}

/**
 * Today's date as an ISO string (YYYY-MM-DD).
 * @returns {string}
 */
export function todayISO() {
    return new Date().toISOString().split('T')[0];
}
