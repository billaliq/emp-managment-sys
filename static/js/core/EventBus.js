/**
 * EventBus.js — Lightweight publish/subscribe event bus (MVC Core)
 *
 * Used for cross-module communication without direct coupling.
 *
 * Example:
 *   // In DepartmentController:
 *   EventBus.emit('department:created', { department });
 *
 *   // In DashboardController:
 *   EventBus.on('department:created', ({ department }) => this.refreshCharts());
 *
 * Internally uses the DOM's CustomEvent mechanism so it integrates seamlessly
 * with the existing browser event model and requires no external libraries.
 */

const BUS_TARGET = document; // single shared target for all events

const EventBus = {
    /**
     * Subscribe to a named event.
     * @param {string}   event    Event name (e.g. 'department:created')
     * @param {Function} handler  Receives the event detail as its only argument
     * @returns {Function}        Unsubscribe function — call it to remove the listener
     */
    on(event, handler) {
        const wrapped = (e) => handler(e.detail);
        BUS_TARGET.addEventListener(event, wrapped);
        return () => BUS_TARGET.removeEventListener(event, wrapped);
    },

    /**
     * Subscribe to a named event exactly once.
     * @param {string}   event
     * @param {Function} handler
     */
    once(event, handler) {
        const wrapped = (e) => handler(e.detail);
        BUS_TARGET.addEventListener(event, wrapped, { once: true });
    },

    /**
     * Publish a named event with optional data.
     * @param {string} event
     * @param {any}    [detail]
     */
    emit(event, detail = null) {
        BUS_TARGET.dispatchEvent(new CustomEvent(event, { detail, bubbles: false }));
    },

    /**
     * Remove all listeners for a named event (use sparingly).
     * NOTE: This clones and replaces the target element which is heavy —
     * prefer keeping unsubscribe functions from `on()` instead.
     */
    off(event, handler) {
        BUS_TARGET.removeEventListener(event, handler);
    },
};

export default EventBus;

/**
 * Pre-defined event name constants to prevent typos.
 * Import and use these instead of raw strings in controllers.
 */
export const Events = {
    // Departments
    DEPT_CREATED:    'department:created',
    DEPT_UPDATED:    'department:updated',
    DEPT_DELETED:    'department:deleted',

    // Employees
    EMP_CREATED:     'employee:created',
    EMP_UPDATED:     'employee:updated',
    EMP_DELETED:     'employee:deleted',

    // Attendance
    ATTEND_UPDATED:  'attendance:updated',
    ATTEND_FILTERED: 'attendance:filtered',

    // Loans
    LOAN_CREATED:    'loan:created',
    LOAN_UPDATED:    'loan:updated',

    // Teams
    TEAM_CREATED:    'team:created',
    TEAM_UPDATED:    'team:updated',
    TEAM_DELETED:    'team:deleted',

    // Payroll
    PAYROLL_UPDATED: 'payroll:updated',

    // UI
    THEME_CHANGED:   'ui:themeChanged',
    PAGE_LOADING:    'ui:pageLoading',
    PAGE_READY:      'ui:pageReady',
};
