/**
 * DashboardController.js — Orchestrates DashboardView (MVC Controller)
 */

import { BaseController } from '../core/BaseController.js';
import { DashboardView }  from '../views/DashboardView.js';
import EventBus, { Events } from '../core/EventBus.js';

export class DashboardController extends BaseController {
    constructor() {
        // Dashboard has no dedicated model (data comes from Django template context)
        super(null, new DashboardView());
    }

    init() {
        const v = this.view;

        v.bindSidebarToggle();
        v.bindSubmenuToggles();
        v.bindDropdowns();
        v.bindLogout();
        v.bindScrollAnimations();

        // Charts — data injected by Django template as global JS variables
        this._tryInitCharts();

        // Re-init charts when theme changes (EventBus or storage event)
        EventBus.on(Events.THEME_CHANGED, () => {
            this._tryInitCharts();
        });
        window.addEventListener('storage', e => {
            if (e.key === 'theme') this._tryInitCharts();
        });

        v.bindChartDownload(window.departmentStats);
    }

    _tryInitCharts(retries = 0) {
        if (typeof Chart === 'undefined') {
            if (retries < 20) setTimeout(() => this._tryInitCharts(retries + 1), 200);
            return;
        }
        const deptStats   = window.departmentStats;
        const genderStats = window.genderStats;
        if (typeof deptStats === 'undefined' || typeof genderStats === 'undefined') {
            if (retries < 20) setTimeout(() => this._tryInitCharts(retries + 1), 100);
            return;
        }
        setTimeout(() => this.view.refreshCharts(deptStats, genderStats), 150);
    }
}
