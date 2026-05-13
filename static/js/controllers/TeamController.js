/**
 * TeamController.js — Orchestrates TeamModel + TeamView (MVC Controller)
 */

import { BaseController } from '../core/BaseController.js';
import { TeamModel }      from '../models/TeamModel.js';
import { TeamView }       from '../views/TeamView.js';
import { EmployeeModel }  from '../models/EmployeeModel.js';

export class TeamController extends BaseController {
    constructor() {
        super(new TeamModel(), new TeamView());
        this.employeeModel = new EmployeeModel();
    }

    init() {
        const v = this.view;

        // Hide loading overlay
        setTimeout(() => {
            const loading = document.getElementById('loading');
            if (loading) { loading.style.opacity = '0'; setTimeout(() => loading.style.display = 'none', 300); }
        }, 1000);

        // ── Add team modal ─────────────────────────
        const openAdd = () => v.openAddTeamModal();
        document.getElementById('addTeamBtn')?.addEventListener('click', openAdd);
        document.getElementById('addFirstTeamBtn')?.addEventListener('click', () =>
            document.getElementById('addTeamBtn')?.click()
        );
        document.getElementById('closeModal')?.addEventListener('click', () => v.closeAddTeamModal());
        document.getElementById('cancelBtn')?.addEventListener('click',  () => v.closeAddTeamModal());
        v.bindBackdropClose(v.addTeamModal, () => v.closeAddTeamModal());

        // Member search in add team modal
        v.bindMembersSearch();

        // Tab switching inside management modal
        v.bindTabSwitching();

        // ── Management modal: open via Manage btn ──
        document.querySelectorAll('.manage-team-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const teamId   = btn.getAttribute('data-team-id');
                const teamName = btn.getAttribute('data-team-name');
                const leader   = btn.getAttribute('data-team-leader');
                v.openManagementModal(teamId, teamName, leader);
                this._loadTeamDetails(teamId);
            });
        });

        // Management modal close
        document.getElementById('closeTeamManagementModal')?.addEventListener('click', () => v.closeManagementModal());
        document.getElementById('cancelTeamSettingsBtn')?.addEventListener('click',    () => v.closeManagementModal());
        v.bindBackdropClose(v.managementModal, () => v.closeManagementModal());

        // ── Team settings form ─────────────────────
        document.getElementById('teamSettingsForm')?.addEventListener('submit', e => {
            e.preventDefault();
            this._handleSaveSettings(e.target);
        });

        // ── Add member button ──────────────────────
        document.getElementById('addMemberBtn')?.addEventListener('click', () => this._handleAddMember());

        // ── Add project button ─────────────────────
        document.getElementById('addProjectBtn')?.addEventListener('click', () => {
            const teamId = document.getElementById('teamIdInput')?.value;
            if (!teamId) { v.showNotification('No team selected', 'error'); return; }
            v.showAddProjectDialog(teamId, data => this._handleCreateProject(data));
        });

        // ── Delete team buttons ────────────────────
        document.querySelectorAll('.delete-team-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const teamId   = btn.getAttribute('data-team-id');
                const teamName = btn.getAttribute('data-team-name');
                this._handleDeleteTeam(teamId, teamName);
            });
        });

        // ── Member details modal ───────────────────
        document.getElementById('closeMemberModal')?.addEventListener('click', () => v.closeMemberDetailsModal());
        v.bindBackdropClose(v.memberDetailsModal, () => v.closeMemberDetailsModal());

        // ── Management modal: delegate remove-member / view-member clicks ──
        v.teamMembersList?.addEventListener('click', e => {
            const memberId = e.target.closest('[data-member-id]')?.getAttribute('data-member-id');
            if (!memberId) return;
            if (e.target.closest('.view-member-details')) this._handleViewMember(memberId);
            if (e.target.closest('.remove-member'))       this._handleRemoveMember(memberId);
        });
    }

    // ── Private handlers ──────────────────────────

    async _loadTeamDetails(teamId) {
        try {
            const data = await this.model.getById(teamId);
            if (data.success) {
                this.view.populateManagementModal(data.team);
                this._loadAttendance(teamId);
            } else {
                this.view.showNotification(data.message || 'Error loading team details', 'error');
            }
        } catch (err) {
            this.handleError(err, 'Loading team details');
        }
    }

    async _loadAttendance(teamId) {
        try {
            const data = await this.model.getAttendance(teamId);
            if (data.attendance) {
                this.view.updateAttendanceBadges(data.attendance);
            }
        } catch {
            // Non-critical — silently skip if endpoint not available
        }
    }

    async _handleSaveSettings(formEl) {
        const fd   = new FormData(formEl);
        const data = {
            team_id:    fd.get('team_id'),
            team_name:  fd.get('team_name'),
            team_lead:  fd.get('team_lead'),
            department: fd.get('department'),
            status:     fd.get('status'),
        };
        const btn = formEl.querySelector('button[type="submit"]');
        this.view.setButtonLoading(btn, true, 'Saving...');
        try {
            const res = await this.model.update(data);
            if (res.success) {
                this.view.showNotification('Team settings saved!', 'success');
                this.view.closeManagementModal();
                setTimeout(() => window.location.reload(), 1000);
            } else {
                this.view.showNotification(res.message || 'Error saving settings', 'error');
            }
        } catch (err) {
            this.handleError(err, 'Saving team settings');
        } finally {
            this.view.setButtonLoading(btn, false);
        }
    }

    async _handleAddMember() {
        const teamId = document.getElementById('teamIdInput')?.value;
        if (!teamId) { this.view.showNotification('No team selected', 'error'); return; }

        const btn = document.getElementById('addMemberBtn');
        this.view.setButtonLoading(btn, true, 'Loading...');
        try {
            const data = await this.employeeModel.getAvailable(teamId);
            this.view.setButtonLoading(btn, false);
            this.view.showAddMemberDialog(
                data.success ? (data.employees || []) : [],
                teamId,
                async (memberIds) => {
                    try {
                        const res = await this.model.addMembers(teamId, memberIds);
                        if (res.success) {
                            this.view.showNotification(res.message || 'Members added!', 'success');
                            this._loadTeamDetails(teamId);
                        } else {
                            this.view.showNotification(res.message || 'Error adding members', 'error');
                        }
                    } catch (err) {
                        this.handleError(err, 'Adding members');
                    }
                }
            );
        } catch (err) {
            this.view.setButtonLoading(btn, false);
            this.handleError(err, 'Loading available employees');
        }
    }

    async _handleRemoveMember(memberId) {
        const teamId = document.getElementById('teamIdInput')?.value;
        if (!confirm('Remove this member from the team?')) return;
        try {
            const data = await this.model.removeMember(teamId, memberId);
            if (data.success) {
                this.view.showNotification('Member removed!', 'success');
                this._loadTeamDetails(teamId);
            } else {
                this.view.showNotification(data.message || 'Error removing member', 'error');
            }
        } catch (err) {
            this.handleError(err, 'Removing member');
        }
    }

    async _handleViewMember(memberId) {
        try {
            const data = await this.employeeModel.getById(memberId);
            if (data.success) this.view.showMemberDetails(data.member);
            else this.view.showNotification(data.message || 'Error loading member', 'error');
        } catch (err) {
            this.handleError(err, 'Loading member details');
        }
    }

    async _handleCreateProject(projectData) {
        try {
            const data = await this.model.addProject(projectData);
            if (data.success) {
                this.view.showNotification(data.message || 'Project created!', 'success');
                this._loadTeamDetails(projectData.team_id);
            } else {
                this.view.showNotification(data.message || 'Error creating project', 'error');
            }
        } catch (err) {
            this.handleError(err, 'Creating project');
        }
    }

    async _handleDeleteTeam(teamId, teamName) {
        if (!confirm(`Are you sure you want to delete team "${teamName}"? This cannot be undone.`)) return;
        try {
            const data = await this.model.delete(teamId);
            if (data.success) {
                this.view.showNotification(data.message || 'Team deleted!', 'success');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                this.view.showNotification(data.message || 'Error deleting team', 'error');
            }
        } catch (err) {
            this.handleError(err, 'Deleting team');
        }
    }
}
