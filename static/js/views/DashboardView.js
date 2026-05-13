/**
 * DashboardView.js — DOM rendering layer for Dashboard (MVC View)
 */

import { BaseView } from '../core/BaseView.js';
import { hexToRgba, getCssVar } from '../core/Utils.js';

export class DashboardView extends BaseView {
    constructor() {
        super();
        this._deptChartInstance   = null;
        this._genderChartInstance = null;
    }

    // ── Sidebar / nav ─────────────────────────────
    bindSidebarToggle() {
        const toggle  = document.getElementById('menuToggle');
        const sidebar = document.getElementById('sidebar');
        if (toggle && sidebar) {
            toggle.addEventListener('click', () => sidebar.classList.toggle('active'));
        }
    }

    bindSubmenuToggles() {
        [
            ['employeesMenu',  'employeesSubmenu'],
            ['attendanceMenu', 'attendanceSubmenu'],
            ['deviceMenu',     'deviceSubmenu'],
        ].forEach(([menuId, subId]) => {
            const menu = document.getElementById(menuId);
            const sub  = document.getElementById(subId);
            if (menu && sub) {
                menu.addEventListener('click', e => {
                    e.preventDefault();
                    menu.classList.toggle('expanded');
                    sub.classList.toggle('expanded');
                });
            }
        });
    }

    // ── User / notification dropdowns ─────────────
    bindDropdowns() {
        const userProfile         = document.getElementById('userProfile');
        const userDropdown        = document.getElementById('userDropdown');
        const notificationBtn     = document.getElementById('notificationBtn');
        const notificationDropdown = document.getElementById('notificationDropdown');

        if (userProfile && userDropdown) {
            userProfile.addEventListener('click', e => {
                e.stopPropagation();
                userDropdown.classList.toggle('active');
                notificationDropdown?.classList.remove('active');
            });
        }

        document.addEventListener('click', e => {
            if (notificationBtn && notificationDropdown) {
                const wrapper = notificationBtn.closest('.notification-wrapper');
                const outside = wrapper ? !wrapper.contains(e.target) : !notificationBtn.contains(e.target);
                if (outside && !notificationDropdown.contains(e.target)) {
                    notificationDropdown.classList.remove('active');
                }
            }
            if (userProfile && userDropdown) {
                if (!userProfile.contains(e.target) && !userDropdown.contains(e.target)) {
                    userDropdown.classList.remove('active');
                }
            }
        });
    }

    // ── Logout ────────────────────────────────────
    bindLogout() {
        window.confirmLogout = () => {
            const confirmed = confirm('Are you sure you want to logout?');
            if (confirmed) {
                document.querySelectorAll('.logout-link, .logout-item').forEach(link => {
                    link.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Logging out...';
                    link.style.pointerEvents = 'none';
                });
            }
            return confirmed;
        };
        document.addEventListener('keydown', e => {
            if (e.ctrlKey && e.key === 'q') {
                e.preventDefault();
                if (window.confirmLogout()) window.location.href = '/logout/';
            }
        });
    }

    // ── Scroll animations ─────────────────────────
    bindScrollAnimations() {
        const animate = () => {
            document.querySelectorAll('.fade-in-up').forEach(el => {
                if (el.getBoundingClientRect().top < window.innerHeight / 1.3) {
                    el.style.opacity    = '1';
                    el.style.transform  = 'translateY(0)';
                }
            });
        };
        animate();
        window.addEventListener('scroll', animate);
    }

    // ── Charts ────────────────────────────────────
    _getThemeColors() {
        const primary   = getCssVar('--primary-color')   || '#667eea';
        const secondary = getCssVar('--secondary-color') || '#764ba2';
        const accent    = getCssVar('--accent-color')    || '#f093fb';
        return {
            primaryRgba:   hexToRgba(primary,   0.7),
            primaryRgb:    hexToRgba(primary,   1),
            secondaryRgba: hexToRgba(secondary, 0.7),
            secondaryRgb:  hexToRgba(secondary, 1),
            accentRgba:    hexToRgba(accent,    0.7),
            accentRgb:     hexToRgba(accent,    1),
        };
    }

    initDepartmentChart(departmentStats) {
        if (!departmentStats?.length) return;
        const ctx = document.getElementById('departmentChart');
        if (!ctx) return;
        if (this._deptChartInstance) { this._deptChartInstance.destroy(); this._deptChartInstance = null; }
        const c = this._getThemeColors();
        this._deptChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels:   departmentStats.map(d => d.name),
                datasets: [{ label: 'Number of Employees', data: departmentStats.map(d => d.employee_count),
                             backgroundColor: c.primaryRgba, borderColor: c.primaryRgb, borderWidth: 1 }],
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } },
        });
    }

    initGenderChart(genderStats) {
        if (!genderStats?.length) return;
        const ctx = document.getElementById('genderChart');
        if (!ctx) return;
        if (this._genderChartInstance) { this._genderChartInstance.destroy(); this._genderChartInstance = null; }
        const c = this._getThemeColors();
        this._genderChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels:   genderStats.map(g => g.gender || 'Not Specified'),
                datasets: [{ data: genderStats.map(g => g.count),
                             backgroundColor: [c.primaryRgba, c.accentRgba, c.secondaryRgba],
                             borderColor:     [c.primaryRgb,  c.accentRgb,  c.secondaryRgb],
                             borderWidth: 1 }],
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } },
        });
    }

    refreshCharts(departmentStats, genderStats) {
        this.initDepartmentChart(departmentStats);
        this.initGenderChart(genderStats);
    }

    bindChartDownload(departmentStats) {
        const btn = document.getElementById('downloadDepartmentChart');
        if (btn) {
            btn.addEventListener('click', () => {
                if (!this._deptChartInstance) return;
                const link = document.createElement('a');
                link.download = `dept-chart-${new Date().toISOString().split('T')[0]}.png`;
                link.href = this._deptChartInstance.toBase64Image();
                document.body.appendChild(link); link.click(); document.body.removeChild(link);
            });
        }
    }
}
