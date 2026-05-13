/**
 * ReportsController.js — Orchestrates ReportsModel + ReportsView (MVC Controller)
 */

import { BaseController } from '../core/BaseController.js';
import { ReportsModel }   from '../models/ReportsModel.js';
import { ReportsView }    from '../views/ReportsView.js';
import { debounce }       from '../core/Utils.js';

export class ReportsController extends BaseController {
    constructor() {
        super(new ReportsModel(), new ReportsView());
    }

    init() {
        const v = this.view;

        // Filter form submit
        v.filterForm?.addEventListener('submit', e => {
            e.preventDefault();
            this._fetchReport();
        });

        // Auto-apply on select changes (debounced)
        const autoFetch = debounce(() => this._fetchReport(), 400);
        v.filterForm?.querySelectorAll('select, input[type="date"]').forEach(el =>
            el.addEventListener('change', autoFetch)
        );
    }

    async _fetchReport() {
        const v = this.view;
        v.showLoading();
        try {
            const fd     = new FormData(v.filterForm);
            const params = new URLSearchParams(fd);
            const data   = await this.model.fetch(params);
            v.renderResults(data.records || []);
        } catch (err) {
            this.handleError(err, 'Fetching report data');
        }
    }
}
