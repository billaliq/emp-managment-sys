/**
 * SettingsView.js — DOM rendering layer for Settings (MVC View)
 */

import { BaseView } from '../core/BaseView.js';

export class SettingsView extends BaseView {
    constructor() {
        super();
        this.tabs        = document.querySelectorAll('.settings-tab');
        this.tabPanels   = document.querySelectorAll('.settings-panel');
    }

    bindTabSwitching() {
        this.tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const target = tab.getAttribute('data-tab');
                this.tabs.forEach(t => t.classList.remove('active'));
                this.tabPanels.forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(`${target}-panel`)?.classList.add('active');
            });
        });
    }

    setSaveLoading(formEl, isLoading) {
        const btn = formEl?.querySelector('button[type="submit"]');
        this.setButtonLoading(btn, isLoading, 'Saving...');
    }
}
