/**
 * BaseView.js — Abstract base class for all MVC Views (MVC Core)
 *
 * Responsibilities:
 *  - All DOM manipulation helpers
 *  - Shared notification / toast system
 *  - Modal open/close helpers
 *  - Button loading-state helper
 *  - No API / fetch knowledge
 */

export class BaseView {
    constructor() {
        /** @type {HTMLElement|null} Container for toast notifications */
        this._notifContainer = null;
    }

    // ─────────────────────────────────────────────
    // Notification / Toast
    // ─────────────────────────────────────────────

    /**
     * Display a toast notification.
     * @param {string} message
     * @param {'success'|'error'|'warning'|'info'} type
     * @param {number} duration  ms before auto-dismiss (0 = no auto-dismiss)
     */
    showNotification(message, type = 'info', duration = 4500) {
        const container = this._getNotifContainer();

        const icons = {
            success: 'fas fa-check-circle',
            error:   'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info:    'fas fa-info-circle',
        };

        const el = document.createElement('div');
        el.className = `notification ${type}`;
        el.innerHTML = `
            <div class="notification-content">
                <i class="${icons[type] || icons.info}"></i>
                <span>${message}</span>
            </div>
            <button class="notification-close" aria-label="Dismiss">
                <i class="fas fa-times"></i>
            </button>
        `;

        container.appendChild(el);
        // Trigger CSS transition
        requestAnimationFrame(() => el.classList.add('show'));

        const dismiss = () => this._dismissNotification(el);
        el.querySelector('.notification-close').addEventListener('click', dismiss);
        if (duration > 0) setTimeout(dismiss, duration);

        return el;
    }

    /** @private */
    _dismissNotification(el) {
        el.classList.remove('show');
        el.addEventListener('transitionend', () => el.remove(), { once: true });
        // Fallback in case transitionend never fires
        setTimeout(() => el.remove(), 500);
    }

    /** @private — lazily create the notification container */
    _getNotifContainer() {
        if (!this._notifContainer || !document.body.contains(this._notifContainer)) {
            let container = document.getElementById('notificationContainer');
            if (!container) {
                container = document.createElement('div');
                container.id = 'notificationContainer';
                container.style.cssText = `
                    position: fixed;
                    top: 1.5rem;
                    right: 1.5rem;
                    z-index: 9999;
                    display: flex;
                    flex-direction: column;
                    gap: 0.75rem;
                    pointer-events: none;
                `;
                document.body.appendChild(container);
            }
            this._notifContainer = container;
        }
        return this._notifContainer;
    }

    // ─────────────────────────────────────────────
    // Modal helpers
    // ─────────────────────────────────────────────

    /**
     * Open a modal element (adds 'active' class, locks body scroll).
     * @param {HTMLElement} modalEl
     */
    openModal(modalEl) {
        if (!modalEl) return;
        modalEl.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    /**
     * Close a modal element.
     * @param {HTMLElement} modalEl
     */
    closeModal(modalEl) {
        if (!modalEl) return;
        modalEl.classList.remove('active');
        document.body.style.overflow = '';
    }

    /**
     * Attach a backdrop-click listener to close a modal.
     * @param {HTMLElement} modalEl
     * @param {Function} [callback]  called after close; defaults to closeModal
     */
    bindBackdropClose(modalEl, callback) {
        if (!modalEl) return;
        modalEl.addEventListener('click', (e) => {
            if (e.target === modalEl) {
                if (typeof callback === 'function') callback();
                else this.closeModal(modalEl);
            }
        });
    }

    // ─────────────────────────────────────────────
    // Button loading state
    // ─────────────────────────────────────────────

    /**
     * Toggle a button's loading state.
     * @param {HTMLElement} btn
     * @param {boolean} isLoading
     * @param {string} [loadingLabel]  shown while loading
     */
    setButtonLoading(btn, isLoading, loadingLabel = 'Saving...') {
        if (!btn) return;
        if (isLoading) {
            btn._originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${loadingLabel}`;
        } else {
            btn.disabled = false;
            btn.innerHTML = btn._originalHtml || loadingLabel;
        }
    }

    // ─────────────────────────────────────────────
    // DOM helpers
    // ─────────────────────────────────────────────

    /**
     * Safely query a DOM element, returning null (not throwing) if not found.
     * @param {string} selector
     * @param {Element} [context]
     * @returns {Element|null}
     */
    $(selector, context = document) {
        return context.querySelector(selector);
    }

    /**
     * Query all matching DOM elements.
     * @param {string} selector
     * @param {Element} [context]
     * @returns {NodeList}
     */
    $$(selector, context = document) {
        return context.querySelectorAll(selector);
    }

    /**
     * Set inner HTML of an element if it exists.
     * @param {string|Element} target  selector string or element
     * @param {string} html
     */
    setHtml(target, html) {
        const el = typeof target === 'string' ? document.querySelector(target) : target;
        if (el) el.innerHTML = html;
    }

    /**
     * Set text content of an element if it exists.
     * @param {string|Element} target
     * @param {string} text
     */
    setText(target, text) {
        const el = typeof target === 'string' ? document.querySelector(target) : target;
        if (el) el.textContent = text;
    }

    /**
     * Show or hide an element via display style.
     * @param {Element} el
     * @param {boolean} visible
     * @param {string} [displayValue]  e.g. 'block', 'flex'
     */
    setVisible(el, visible, displayValue = 'block') {
        if (!el) return;
        el.style.display = visible ? displayValue : 'none';
    }

    /**
     * Emit a custom DOM event (for cross-component communication).
     * @param {string} eventName
     * @param {any} detail
     */
    emit(eventName, detail = null) {
        document.dispatchEvent(new CustomEvent(eventName, { detail, bubbles: true }));
    }

    /**
     * Listen for a custom DOM event.
     * @param {string} eventName
     * @param {Function} handler
     */
    on(eventName, handler) {
        document.addEventListener(eventName, handler);
    }
}
