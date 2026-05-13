/**
 * BaseController.js — Abstract base class for all MVC Controllers (MVC Core)
 *
 * Responsibilities:
 *  - Holds references to a Model and a View
 *  - Provides an init() lifecycle hook
 *  - Provides shared error-handling helper
 *  - Subclasses override init() to wire up event listeners
 */

export class BaseController {
    /**
     * @param {import('./BaseModel.js').BaseModel} model
     * @param {import('./BaseView.js').BaseView}   view
     */
    constructor(model, view) {
        this.model = model;
        this.view  = view;
    }

    /**
     * Initialise the controller.
     * Subclasses must override this to attach all event listeners.
     */
    init() {
        throw new Error(`${this.constructor.name}.init() must be implemented.`);
    }

    /**
     * Centralised error handler.
     * Logs to console and shows a notification via the view.
     * @param {Error|string} err
     * @param {string} [context]  Short description of what was being attempted
     */
    handleError(err, context = '') {
        const msg = err instanceof Error ? err.message : String(err);
        console.error(`[${this.constructor.name}]${context ? ' ' + context : ''}:`, err);
        if (this.view && typeof this.view.showNotification === 'function') {
            this.view.showNotification(
                context ? `${context}: ${msg}` : msg,
                'error'
            );
        }
    }
}
