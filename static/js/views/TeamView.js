/**
 * TeamView.js — DOM rendering layer for Teams (MVC View)
 */

import { BaseView } from '../core/BaseView.js';
import { escapeHtml } from '../core/Utils.js';

export class TeamView extends BaseView {
    constructor() {
        super();
        this.addTeamModal         = document.getElementById('addTeamModal');
        this.managementModal      = document.getElementById('teamManagementModal');
        this.memberDetailsModal   = document.getElementById('memberDetailsModal');
        this.teamMembersList      = document.getElementById('teamMembersList');
        this.teamProjectsList     = document.getElementById('teamProjectsList');
        this.teamManagementTitle  = document.getElementById('teamManagementTitle');
        this.teamNameDisplay      = document.getElementById('teamNameDisplay');
        this.teamLeaderDisplay    = document.getElementById('teamLeaderDisplay');
        this.teamLeaderAvatar     = document.getElementById('teamLeaderAvatar');
        this.memberDetailsBody    = document.getElementById('memberDetailsBody');
        this.memberDetailsTitle   = document.getElementById('memberDetailsTitle');
        this.tabs                 = document.querySelectorAll('.tab');
        this.tabContents          = document.querySelectorAll('.tab-content');
    }

    // ── Add team modal ────────────────────────────
    openAddTeamModal()  { this.openModal(this.addTeamModal); }
    closeAddTeamModal() { this.closeModal(this.addTeamModal); }

    bindMembersSearch() {
        const input  = document.getElementById('teamMembersSearchInput');
        const select = document.getElementById('teamMembersSelect');
        if (!input || !select) return;
        input.addEventListener('input', function () {
            const term = this.value.toLowerCase().trim();
            Array.from(select.options).forEach(opt => {
                opt.style.display = !term || opt.textContent.toLowerCase().includes(term) ? '' : 'none';
            });
        });
    }

    // ── Tab switching ─────────────────────────────
    bindTabSwitching() {
        this.tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabId = tab.getAttribute('data-tab');
                this.tabs.forEach(t => t.classList.remove('active'));
                this.tabContents.forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(`${tabId}-tab`)?.classList.add('active');
            });
        });
    }

    // ── Team management modal ─────────────────────
    openManagementModal(teamId, teamName, teamLeader) {
        if (this.teamManagementTitle) this.teamManagementTitle.textContent = `Manage ${teamName}`;
        if (this.teamNameDisplay)     this.teamNameDisplay.textContent = teamName;
        if (this.teamLeaderDisplay)   this.teamLeaderDisplay.textContent = teamLeader;
        if (this.teamLeaderAvatar) {
            this.teamLeaderAvatar.textContent = teamLeader.split(' ').map(n => n[0]).join('').toUpperCase();
        }
        const teamIdInput = document.getElementById('teamIdInput');
        const teamNameInput = document.getElementById('teamNameInput');
        if (teamIdInput)   teamIdInput.value   = teamId;
        if (teamNameInput) teamNameInput.value = teamName;
        this.openModal(this.managementModal);
    }

    closeManagementModal() { this.closeModal(this.managementModal); }

    populateManagementModal(team) {
        if (this.teamManagementTitle) this.teamManagementTitle.textContent = `Manage ${team.name}`;
        if (this.teamNameDisplay)     this.teamNameDisplay.textContent = team.name;
        if (this.teamLeaderDisplay)   this.teamLeaderDisplay.textContent = team.leader.name;
        if (this.teamLeaderAvatar)    this.teamLeaderAvatar.textContent = team.leader.initials;

        const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
        set('teamIdInput',        team.id);
        set('teamNameInput',      team.name);

        const leadSelect = document.getElementById('teamLeadSelect');
        if (leadSelect) {
            leadSelect.value = team.leader?.team_lead_name || team.leader?.id || '';
        }
        if (team.department_id) set('teamDepartmentSelect', team.department_id);
        const statusSel = document.getElementById('teamStatusSelect');
        if (statusSel && team.status) statusSel.value = team.status;

        this._renderMembersList(team.members || [], team.id);
        this._renderProjectsList(team.projects || []);
    }

    _renderMembersList(members, teamId) {
        if (!this.teamMembersList) return;
        this.teamMembersList.innerHTML = '';

        if (!members.length) {
            this.teamMembersList.innerHTML = '<div class="no-data">No members in this team</div>';
            return;
        }

        members.forEach(member => {
            const item = document.createElement('div');
            item.className = 'member-item';
            item.setAttribute('data-member-id', member.id);
            item.innerHTML = `
                <div class="member-info">
                    <div class="member-avatar">${escapeHtml(member.initials || 'ME')}</div>
                    <div>
                        <div style="font-weight:600;">${escapeHtml(member.name || 'Member Name')}</div>
                        <div style="font-size:.85rem;color:var(--text-light);">${escapeHtml(member.role || 'Team Member')}</div>
                        <div class="team-member-attendance" id="modal-attendance-${member.id}">
                            <span class="attendance-badge loading"><i class="fas fa-spinner fa-spin"></i> Loading...</span>
                        </div>
                    </div>
                </div>
                <div class="member-actions">
                    <button class="btn btn-secondary view-member-details" style="padding:.4rem;" data-member-id="${member.id}">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn btn-secondary remove-member" style="padding:.4rem;" data-member-id="${member.id}">
                        <i class="fas fa-user-times"></i>
                    </button>
                </div>`;
            this.teamMembersList.appendChild(item);
        });
    }

    updateAttendanceBadges(attendanceData) {
        attendanceData.forEach(({ memberId, badge }) => {
            const container = document.getElementById(`modal-attendance-${memberId}`);
            if (container) container.innerHTML = badge;
        });
    }

    _renderProjectsList(projects) {
        if (!this.teamProjectsList) return;
        this.teamProjectsList.innerHTML = '';

        if (!projects.length) {
            this.teamProjectsList.innerHTML = '<div class="no-data">No projects assigned to this team</div>';
            return;
        }

        projects.forEach(project => {
            const item = document.createElement('div');
            item.className = 'project-item';
            item.innerHTML = `
                <div class="project-header">
                    <div class="project-title">${escapeHtml(project.name)}</div>
                    <div class="project-status ${project.status === 'active' ? 'status-active' : 'status-completed'}">
                        ${project.status === 'active' ? 'Active' : 'Completed'}
                    </div>
                </div>
                <div class="progress-bar">
                    <div class="progress" style="width:${project.progress || 0}%"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:.85rem;">
                    <span>Progress: ${project.progress || 0}%</span>
                    <span>Due: ${escapeHtml(project.due_date || 'N/A')}</span>
                </div>`;
            this.teamProjectsList.appendChild(item);
        });
    }

    // ── Member details modal ──────────────────────
    showMemberDetails(member) {
        if (this.memberDetailsTitle) {
            this.memberDetailsTitle.textContent = `${member.name} - Details`;
        }
        if (this.memberDetailsBody) {
            const records = member.attendance_records || [];
            const rows = records.length
                ? records.map(r => `
                    <tr>
                        <td style="padding:.75rem;border-bottom:1px solid var(--border-color);">${r.date || 'N/A'}</td>
                        <td style="padding:.75rem;border-bottom:1px solid var(--border-color);">${r.status || 'N/A'}</td>
                        <td style="padding:.75rem;border-bottom:1px solid var(--border-color);">${r.check_in || '-'}</td>
                        <td style="padding:.75rem;border-bottom:1px solid var(--border-color);">${r.check_out || '-'}</td>
                    </tr>`).join('')
                : '<tr><td colspan="4" style="text-align:center;padding:1rem;">No attendance records</td></tr>';

            this.memberDetailsBody.innerHTML = `
                <div style="margin:1.5rem;">
                    <strong>Email:</strong> ${escapeHtml(member.email || 'N/A')}<br>
                    <strong>Phone:</strong> ${escapeHtml(member.phone || 'N/A')}<br>
                    <strong>Department:</strong> ${escapeHtml(member.department || 'N/A')}<br>
                    <strong>Position:</strong> ${escapeHtml(member.position || 'N/A')}<br>
                    <strong>Join Date:</strong> ${escapeHtml(member.join_date || 'N/A')}<br>
                    <strong>Attendance:</strong> ${member.attendance_rate || 0}%<br>
                    <strong>Leaves Taken:</strong> ${member.leaves_taken || 0}<br>
                    <strong>Performance Rating:</strong> ${member.performance_rating || 'N/A'}/5
                </div>
                <h3 style="margin:1.5rem 1.5rem .5rem;">Recent Attendance</h3>
                <table class="table" style="margin:1.5rem;width:calc(100% - 3rem);border-collapse:collapse;">
                    <thead>
                        <tr>
                            <th style="padding:.75rem;border-bottom:1px solid var(--border-color);">Date</th>
                            <th style="padding:.75rem;border-bottom:1px solid var(--border-color);">Status</th>
                            <th style="padding:.75rem;border-bottom:1px solid var(--border-color);">Check-in</th>
                            <th style="padding:.75rem;border-bottom:1px solid var(--border-color);">Check-out</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>`;
        }
        this.openModal(this.memberDetailsModal);
    }

    closeMemberDetailsModal() { this.closeModal(this.memberDetailsModal); }

    // ── Add member dialog ─────────────────────────
    showAddMemberDialog(employees, teamId, onConfirm) {
        const existing = document.getElementById('addMemberDialog');
        if (existing) existing.remove();

        const select = document.createElement('select');
        select.multiple = true;
        select.style.cssText = 'height:120px;width:100%;margin-bottom:1rem;padding:.5rem;border:1px solid #ddd;border-radius:4px;';

        if (employees.length) {
            employees.forEach(emp => {
                const opt = document.createElement('option');
                opt.value = emp.id;
                opt.textContent = `${emp.name} (${emp.role || 'Employee'})`;
                select.appendChild(opt);
            });
        } else {
            select.innerHTML = '<option disabled>No available employees</option>';
        }

        const dialog = document.createElement('div');
        dialog.id = 'addMemberDialog';
        dialog.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:white;padding:2rem;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,.15);z-index:10000;min-width:400px;max-width:500px;';
        dialog.innerHTML = `
            <h3 style="margin-bottom:1rem;">Add Members to Team</h3>
            <input type="text" id="memberSearchInput" class="form-input" placeholder="Search employees..." style="margin-bottom:.75rem;">
            <p style="margin-bottom:1rem;font-size:.9rem;color:#666;">Hold Ctrl/Cmd to select multiple members</p>
            <div style="display:flex;gap:1rem;margin-top:1.5rem;">
                <button id="dialogCancel" class="btn btn-secondary" style="flex:1;">Cancel</button>
                <button id="dialogConfirm" class="btn btn-primary" style="flex:1;">Add Selected</button>
            </div>`;
        dialog.insertBefore(select, dialog.querySelector('p'));
        document.body.appendChild(dialog);

        document.getElementById('memberSearchInput').addEventListener('input', function () {
            const term = this.value.toLowerCase();
            Array.from(select.options).forEach(opt => {
                opt.style.display = opt.textContent.toLowerCase().includes(term) ? '' : 'none';
            });
        });

        document.getElementById('dialogCancel').addEventListener('click', () => dialog.remove());
        document.getElementById('dialogConfirm').addEventListener('click', () => {
            const ids = Array.from(select.selectedOptions)
                .map(o => parseInt(o.value)).filter(id => !isNaN(id));
            if (!ids.length) { this.showNotification('Please select at least one member', 'warning'); return; }
            dialog.remove();
            onConfirm(ids);
        });
    }

    // ── Add project dialog ────────────────────────
    showAddProjectDialog(teamId, onConfirm) {
        const existing = document.getElementById('addProjectDialog');
        if (existing) existing.remove();

        const dialog = document.createElement('div');
        dialog.id = 'addProjectDialog';
        dialog.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:white;padding:2rem;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,.15);z-index:10000;min-width:400px;max-width:500px;';
        dialog.innerHTML = `
            <h3 style="margin-bottom:1rem;">Add Project</h3>
            <div class="form-group"><label class="form-label">Project Name</label><input type="text" id="projectNameInput" class="form-input" placeholder="Enter project name"></div>
            <div class="form-group"><label class="form-label">Description</label><textarea id="projectDescriptionInput" class="form-textarea" rows="3" placeholder="Optional description"></textarea></div>
            <div class="form-group"><label class="form-label">Start Date</label><input type="date" id="projectStartDateInput" class="form-input"></div>
            <div class="form-group"><label class="form-label">End Date</label><input type="date" id="projectEndDateInput" class="form-input"></div>
            <div class="form-group"><label class="form-label">Status</label>
                <select id="projectStatusSelect" class="form-select">
                    <option value="planning">Planning</option><option value="active" selected>Active</option>
                    <option value="on_hold">On Hold</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option>
                </select>
            </div>
            <div class="form-group"><label class="form-label">Initial Progress (%)</label><input type="number" id="projectProgressInput" class="form-input" value="0" min="0" max="100"></div>
            <div style="display:flex;gap:1rem;margin-top:1.5rem;">
                <button id="projectDialogCancel" class="btn btn-secondary" style="flex:1;">Cancel</button>
                <button id="projectDialogConfirm" class="btn btn-primary" style="flex:1;">Create Project</button>
            </div>`;
        document.body.appendChild(dialog);

        document.getElementById('projectDialogCancel').addEventListener('click', () => dialog.remove());
        document.getElementById('projectDialogConfirm').addEventListener('click', () => {
            const name = document.getElementById('projectNameInput').value.trim();
            if (!name) { this.showNotification('Project name is required', 'error'); return; }
            dialog.remove();
            onConfirm({
                team_id:     parseInt(teamId),
                name,
                description: document.getElementById('projectDescriptionInput').value.trim(),
                start_date:  document.getElementById('projectStartDateInput').value,
                end_date:    document.getElementById('projectEndDateInput').value,
                status:      document.getElementById('projectStatusSelect').value,
                progress:    parseInt(document.getElementById('projectProgressInput').value || '0', 10),
            });
        });
    }
}
