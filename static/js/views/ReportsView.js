/**
 * ReportsView.js — DOM rendering layer for Reports (MVC View)
 */

import { BaseView } from '../core/BaseView.js';

export class ReportsView extends BaseView {
    constructor() {
        super();
        this.filterForm   = document.getElementById('reportFilterForm');
        this.resultsTable = document.getElementById('reportResultsTable');
    }

    showLoading() {
        if (this.resultsTable) {
            const tbody = this.resultsTable.querySelector('tbody');
            if (tbody) tbody.innerHTML =
                '<tr><td colspan="20" class="text-center"><i class="fas fa-spinner fa-spin"></i> Loading...</td></tr>';
        }
    }

    renderResults(records) {
        if (!this.resultsTable) return;
        const tbody = this.resultsTable.querySelector('tbody');
        if (!tbody) return;
        if (!records?.length) {
            tbody.innerHTML = '<tr><td colspan="20" class="text-center">No records found</td></tr>';
            return;
        }
        // Actual row rendering is data-schema dependent;
        // subclasses or report-specific code can override this.
        tbody.innerHTML = records.map(r => `<tr>${Object.values(r).map(v => `<td>${v}</td>`).join('')}</tr>`).join('');
    }
}
