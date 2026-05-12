// team.js
document.addEventListener('DOMContentLoaded', function() {
    // Simulate loading
    setTimeout(() => {
        document.getElementById('loading').style.opacity = '0';
        setTimeout(() => {
            document.getElementById('loading').style.display = 'none';
        }, 300);
    }, 1000);

    // Add first team button functionality
    const addFirstTeamBtn = document.getElementById('addFirstTeamBtn');
    if (addFirstTeamBtn) {
        addFirstTeamBtn.addEventListener('click', () => {
            document.getElementById('addTeamBtn').click();
        });
    }

    // Modal functionality
    const addTeamBtn = document.getElementById('addTeamBtn');
    const addTeamModal = document.getElementById('addTeamModal');
    const closeModal = document.getElementById('closeModal');
    const cancelBtn = document.getElementById('cancelBtn');

    if (addTeamBtn && addTeamModal) {
        addTeamBtn.addEventListener('click', () => {
            addTeamModal.classList.add('active');
        });
    }

    if (closeModal && addTeamModal) {
        closeModal.addEventListener('click', () => {
            addTeamModal.classList.remove('active');
        });
    }

    if (cancelBtn && addTeamModal) {
        cancelBtn.addEventListener('click', () => {
            addTeamModal.classList.remove('active');
        });
    }

    // Close modal when clicking outside
    if (addTeamModal) {
        addTeamModal.addEventListener('click', (e) => {
            if (e.target === addTeamModal) {
                addTeamModal.classList.remove('active');
            }
        });
    }

    // Client-side search for team members in Add Team modal
    const teamMembersSearchInput = document.getElementById('teamMembersSearchInput');
    const teamMembersSelect = document.getElementById('teamMembersSelect');
    if (teamMembersSearchInput && teamMembersSelect) {
        teamMembersSearchInput.addEventListener('input', function() {
            const term = this.value.toLowerCase().trim();
            Array.from(teamMembersSelect.options).forEach(option => {
                const text = option.textContent.toLowerCase();
                option.style.display = term === '' || text.includes(term) ? '' : 'none';
            });
        });
    }

    // Team Management Modal Logic
    const teamManagementModal = document.getElementById('teamManagementModal');
    const closeTeamManagementModal = document.getElementById('closeTeamManagementModal');
    const teamManagementTitle = document.getElementById('teamManagementTitle');
    const teamNameDisplay = document.getElementById('teamNameDisplay');
    const teamLeaderDisplay = document.getElementById('teamLeaderDisplay');
    const teamLeaderAvatar = document.getElementById('teamLeaderAvatar');
    const teamMembersList = document.getElementById('teamMembersList');
    const teamProjectsList = document.getElementById('teamProjectsList');
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');

    // Tab switching functionality
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.getAttribute('data-tab');

            // Remove active class from all tabs and contents
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // Add active class to clicked tab and corresponding content
            tab.classList.add('active');
            document.getElementById(`${tabId}-tab`).classList.add('active');
        });
    });

    // Show team management modal when clicking "Manage" button
    document.querySelectorAll('.manage-team-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const teamId = this.getAttribute('data-team-id');
            const teamName = this.getAttribute('data-team-name');
            const teamLeader = this.getAttribute('data-team-leader');

            console.log('Opening team management for team ID:', teamId);

            // Set basic team info immediately
            teamManagementTitle.textContent = `Manage ${teamName}`;
            teamNameDisplay.textContent = teamName;
            teamLeaderDisplay.textContent = teamLeader;

            // Generate initials for avatar
            const initials = teamLeader.split(' ').map(name => name[0]).join('').toUpperCase();
            teamLeaderAvatar.textContent = initials;

            document.getElementById('teamIdInput').value = teamId;
            document.getElementById('teamNameInput').value = teamName;

            // Fetch team details from server
            fetch(`/teams/${teamId}/details/`, {
                method: 'GET',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                console.log('Team details response:', data);
                if (data.success) {
                    const team = data.team;

                    // Update modal with detailed team info
                    teamManagementTitle.textContent = `Manage ${team.name}`;
                    teamNameDisplay.textContent = team.name;
                    teamLeaderDisplay.textContent = team.leader.name;
                    teamLeaderAvatar.textContent = team.leader.initials;

                    // Update form fields
                    document.getElementById('teamIdInput').value = team.id;
                    document.getElementById('teamNameInput').value = team.name;

                    // Set team lead dropdown - use team_lead_name (TEAM_CHOICES value) if available
                    const teamLeadSelect = document.getElementById('teamLeadSelect');
                    if (teamLeadSelect) {
                        if (team.leader && team.leader.team_lead_name) {
                            // Use TEAM_CHOICES value
                            teamLeadSelect.value = team.leader.team_lead_name;
                        } else if (team.leader && team.leader.id) {
                            // Fallback: try to find by employee ID (if dropdown has employee IDs)
                            teamLeadSelect.value = team.leader.id;
                        } else {
                            teamLeadSelect.value = '';
                        }
                    }

                    if (team.department_id) {
                        document.getElementById('teamDepartmentSelect').value = team.department_id;
                    }

                    // Set status dropdown
                    const statusSelect = document.getElementById('teamStatusSelect');
                    if (statusSelect && team.status) {
                        statusSelect.value = team.status;
                    }

                    // Populate team members
                    teamMembersList.innerHTML = '';
                    if (team.members && team.members.length > 0) {
                        team.members.forEach(member => {
                            const memberItem = document.createElement('div');
                            memberItem.className = 'member-item';
                            memberItem.setAttribute('data-member-id', member.id);
                            memberItem.innerHTML = `
                                <div class="member-info">
                                    <div class="member-avatar">${member.initials || 'ME'}</div>
                                    <div>
                                        <div style="font-weight: 600;">${member.name || 'Member Name'}</div>
                                        <div style="font-size: 0.85rem; color: var(--text-light);">${member.role || 'Team Member'}</div>
                                        <div class="team-member-attendance" id="modal-attendance-${member.id}">
                                            <span class="attendance-badge loading">
                                                <i class="fas fa-spinner fa-spin"></i>
                                                Loading...
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <div class="member-actions">
                                    <button class="btn btn-secondary view-member-details" style="padding: 0.4rem;" data-member-id="${member.id}">
                                        <i class="fas fa-eye"></i>
                                    </button>
                                    <button class="btn btn-secondary remove-member" style="padding: 0.4rem;" data-member-id="${member.id}">
                                        <i class="fas fa-user-times"></i>
                                    </button>
                                </div>
                            `;
                            teamMembersList.appendChild(memberItem);
                        });

                        // Load attendance for team members in modal
                        loadTeamAttendance(team.id);
                    } else {
                        teamMembersList.innerHTML = '<div class="no-data">No members in this team</div>';
                    }

                    // Populate projects
                    teamProjectsList.innerHTML = '';
                    if (team.projects && team.projects.length > 0) {
                        team.projects.forEach(project => {
                            const projectItem = document.createElement('div');
                            projectItem.className = 'project-item';
                            projectItem.innerHTML = `
                                <div class="project-header">
                                    <div class="project-title">${project.name}</div>
                                    <div class="project-status ${project.status === 'active' ? 'status-active' : 'status-completed'}">
                                        ${project.status === 'active' ? 'Active' : 'Completed'}
                                    </div>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress" style="width: ${project.progress || 0}%"></div>
                                </div>
                                <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                                    <span>Progress: ${project.progress || 0}%</span>
                                    <span>Due: ${project.due_date || 'N/A'}</span>
                                </div>
                            `;
                            teamProjectsList.appendChild(projectItem);
                        });
                    } else {
                        teamProjectsList.innerHTML = '<div class="no-data">No projects assigned to this team</div>';
                    }

                    // Show the modal
                    teamManagementModal.classList.add('active');

                    // Add event listeners to the newly created buttons
                    document.querySelectorAll('.view-member-details').forEach(btn => {
                        btn.addEventListener('click', function() {
                            const memberId = this.getAttribute('data-member-id');
                            showMemberDetails(memberId);
                        });
                    });

                    document.querySelectorAll('.remove-member').forEach(btn => {
                        btn.addEventListener('click', function() {
                            const memberId = this.getAttribute('data-member-id');
                            removeTeamMember(teamId, memberId);
                        });
                    });
                } else {
                    console.error('Error loading team details:', data.message);
                    alert('Error loading team details: ' + (data.message || 'Unknown error'));

                    // Show modal even if details fail to load
                    teamManagementModal.classList.add('active');
                }
            })
            .catch(error => {
                console.error('Error fetching team details:', error);
                alert('Error loading team details. Please try again.');

                // Show modal even if fetch fails
                teamManagementModal.classList.add('active');
            });
        });
    });

    // Close team management modal
    if (closeTeamManagementModal && teamManagementModal) {
        closeTeamManagementModal.addEventListener('click', () => {
            teamManagementModal.classList.remove('active');
        });
    }

    if (teamManagementModal) {
        teamManagementModal.addEventListener('click', (e) => {
            if (e.target === teamManagementModal) {
                teamManagementModal.classList.remove('active');
            }
        });
    }

    // Save team settings
    const teamSettingsForm = document.getElementById('teamSettingsForm');
    if (teamSettingsForm) {
        teamSettingsForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const data = {
                team_id: formData.get('team_id'),
                team_name: formData.get('team_name'),
                team_lead: formData.get('team_lead'),
                department: formData.get('department'),
                status: formData.get('status')
            };

            console.log('Saving team settings:', data);

            fetch('/teams/update/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Team settings saved successfully!');
                    teamManagementModal.classList.remove('active');
                    location.reload(); // Reload to see changes
                } else {
                    alert('Error saving team settings: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error saving team settings');
            });
        });
    }

    // Cancel team settings
    const cancelTeamSettingsBtn = document.getElementById('cancelTeamSettingsBtn');
    if (cancelTeamSettingsBtn) {
        cancelTeamSettingsBtn.addEventListener('click', () => {
            teamManagementModal.classList.remove('active');
        });
    }

    // Add member button
    const addMemberBtn = document.getElementById('addMemberBtn');
    if (addMemberBtn) {
        addMemberBtn.addEventListener('click', function() {
            const teamIdInput = document.getElementById('teamIdInput');
            if (!teamIdInput) {
                alert('Team management form not found. Please refresh the page.');
                return;
            }

            const teamId = teamIdInput.value;
            if (!teamId) {
                alert('No team selected');
                return;
            }

            // Show loading state
            this.disabled = true;
            const originalBtnText = this.innerHTML;
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';

            // Get CSRF token
            const csrfToken = csrftoken || getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value;

            // Create select element
            const memberSelect = document.createElement('select');
            memberSelect.multiple = true;
            memberSelect.style.height = '120px';
            memberSelect.style.width = '100%';
            memberSelect.style.marginBottom = '1rem';
            memberSelect.style.padding = '0.5rem';
            memberSelect.style.border = '1px solid #ddd';
            memberSelect.style.borderRadius = '4px';

            // Fetch available employees
            fetch(`/employees/available/?team_id=${teamId}`, {
                method: 'GET',
                headers: {
                    'X-CSRFToken': csrfToken || '',
                    'Content-Type': 'application/json'
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                this.disabled = false;
                this.innerHTML = originalBtnText;

                if (data.success) {
                    if (data.employees && data.employees.length > 0) {
                        data.employees.forEach(employee => {
                            const option = document.createElement('option');
                            option.value = employee.id;
                            option.textContent = `${employee.name} (${employee.role || 'Employee'})`;
                            memberSelect.appendChild(option);
                        });
                    } else {
                        memberSelect.innerHTML = '<option disabled>No available employees</option>';
                    }

                    // Create dialog
                    const dialog = document.createElement('div');
                    dialog.id = 'addMemberDialog';
                    dialog.style.position = 'fixed';
                    dialog.style.top = '50%';
                    dialog.style.left = '50%';
                    dialog.style.transform = 'translate(-50%, -50%)';
                    dialog.style.backgroundColor = 'white';
                    dialog.style.padding = '2rem';
                    dialog.style.borderRadius = '8px';
                    dialog.style.boxShadow = '0 4px 20px rgba(0,0,0,0.15)';
                    dialog.style.zIndex = '10000';
                    dialog.style.minWidth = '400px';
                    dialog.style.maxWidth = '500px';

                    dialog.innerHTML = `
                        <h3 style="margin-bottom: 1rem;">Add Members to Team</h3>
                        <input type="text" id="memberSearchInput" class="form-input" placeholder="Search employees..." style="margin-bottom: 0.75rem;">
                        <p style="margin-bottom: 1rem; font-size: 0.9rem; color: #666;">Hold Ctrl/Cmd to select multiple members</p>
                        <div style="display: flex; gap: 1rem; margin-top: 1.5rem;">
                            <button id="dialogCancel" class="btn btn-secondary" style="flex:1;">Cancel</button>
                            <button id="dialogConfirm" class="btn btn-primary" style="flex:1;">Add Selected</button>
                        </div>
                    `;

                    dialog.insertBefore(memberSelect, dialog.querySelector('p'));
                    document.body.appendChild(dialog);

                    // Simple client-side search in member list
                    const searchInput = document.getElementById('memberSearchInput');
                    if (searchInput) {
                        searchInput.addEventListener('input', function() {
                            const term = this.value.toLowerCase();
                            Array.from(memberSelect.options).forEach(opt => {
                                const text = opt.textContent.toLowerCase();
                                opt.style.display = text.includes(term) ? '' : 'none';
                            });
                        });
                    }

                    // Cancel button handler
                    const cancelBtn = document.getElementById('dialogCancel');
                    if (cancelBtn) {
                        cancelBtn.addEventListener('click', function() {
                            if (document.body.contains(dialog)) {
                                document.body.removeChild(dialog);
                            }
                        });
                    }

                    // Confirm button handler
                    const confirmBtn = document.getElementById('dialogConfirm');
                    if (confirmBtn) {
                        confirmBtn.addEventListener('click', function(e) {
                            e.preventDefault();
                            e.stopPropagation();

                            console.log('Add Selected button clicked');

                            const selectedOptions = memberSelect.selectedOptions;
                            console.log('Selected options:', selectedOptions.length);

                            const selectedMembers = Array.from(selectedOptions).map(option => {
                                const val = parseInt(option.value);
                                if (isNaN(val)) {
                                    console.error('Invalid member ID:', option.value);
                                    return null;
                                }
                                return val;
                            }).filter(id => id !== null);

                            console.log('Selected members (parsed):', selectedMembers);

                            if (selectedMembers.length > 0) {
                                // Disable button and show loading
                                const originalConfirmText = this.innerHTML;
                                this.disabled = true;
                                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';

                                console.log('Adding members:', { team_id: parseInt(teamId), member_ids: selectedMembers });
                                console.log('CSRF Token:', csrfToken ? 'Present' : 'Missing');

                                // Create abort controller for timeout
                                const controller = new AbortController();
                                const timeoutId = setTimeout(() => {
                                    controller.abort();
                                }, 30000); // 30 second timeout

                                fetch('/teams/add-members/', {
                                    method: 'POST',
                                    headers: {
                                        'X-CSRFToken': csrfToken || '',
                                        'Content-Type': 'application/json',
                                        'X-Requested-With': 'XMLHttpRequest'
                                    },
                                    body: JSON.stringify({
                                        team_id: parseInt(teamId),
                                        member_ids: selectedMembers
                                    }),
                                    signal: controller.signal
                                })
                                .then(response => {
                                    clearTimeout(timeoutId);
                                    console.log('Response status:', response.status);
                                    console.log('Response headers:', response.headers);

                                    // Check content type
                                    const contentType = response.headers.get('content-type');
                                    if (!contentType || !contentType.includes('application/json')) {
                                        return response.text().then(text => {
                                            console.error('Non-JSON response:', text);
                                            throw new Error('Server returned non-JSON response');
                                        });
                                    }

                                    if (!response.ok) {
                                        return response.json().then(err => {
                                            throw new Error(err.message || `HTTP error! status: ${response.status}`);
                                        }).catch(parseError => {
                                            console.error('Error parsing error response:', parseError);
                                            throw new Error(`HTTP error! status: ${response.status}`);
                                        });
                                    }
                                    return response.json();
                                })
                                .then(data => {
                                    console.log('Response data:', data);
                                    if (data.success) {
                                        alert(data.message || 'Members added successfully!');
                                        if (document.body.contains(dialog)) {
                                            document.body.removeChild(dialog);
                                        }
                                        // Refresh the team management modal
                                        const manageBtn = document.querySelector(`.manage-team-btn[data-team-id="${teamId}"]`);
                                        if (manageBtn) {
                                            manageBtn.click();
                                        } else {
                                            location.reload();
                                        }
                                    } else {
                                        alert('Error adding members: ' + (data.message || 'Unknown error'));
                                        this.disabled = false;
                                        this.innerHTML = originalConfirmText;
                                    }
                                })
                                .catch(error => {
                                    clearTimeout(timeoutId);
                                    console.error('Error adding members:', error);

                                    let errorMessage = 'Please try again.';
                                    if (error.name === 'AbortError') {
                                        errorMessage = 'Request timed out. Please check your connection and try again.';
                                    } else if (error.message) {
                                        errorMessage = error.message;
                                    }

                                    alert('Error adding members: ' + errorMessage);
                                    this.disabled = false;
                                    this.innerHTML = originalConfirmText;
                                });
                            } else {
                                alert('Please select at least one member');
                            }
                        });
                    }
                } else {
                    alert('Error loading available employees: ' + (data.message || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error loading available employees:', error);
                alert('Error loading available employees: ' + (error.message || 'Please try again.'));
                this.disabled = false;
                this.innerHTML = originalBtnText;
            });
        });
    }

    // Add project button
    const addProjectBtn = document.getElementById('addProjectBtn');
    if (addProjectBtn) {
        addProjectBtn.addEventListener('click', () => {
            const teamId = document.getElementById('teamIdInput')?.value;
            if (!teamId) {
                alert('No team selected');
                return;
            }

            // Simple inline dialog for adding a project
            const dialog = document.createElement('div');
            dialog.id = 'addProjectDialog';
            dialog.style.position = 'fixed';
            dialog.style.top = '50%';
            dialog.style.left = '50%';
            dialog.style.transform = 'translate(-50%, -50%)';
            dialog.style.backgroundColor = 'white';
            dialog.style.padding = '2rem';
            dialog.style.borderRadius = '8px';
            dialog.style.boxShadow = '0 4px 20px rgba(0,0,0,0.15)';
            dialog.style.zIndex = '10000';
            dialog.style.minWidth = '400px';
            dialog.style.maxWidth = '500px';

            dialog.innerHTML = `
                <h3 style="margin-bottom: 1rem;">Add Project</h3>
                <div class="form-group">
                    <label class="form-label">Project Name</label>
                    <input type="text" id="projectNameInput" class="form-input" placeholder="Enter project name">
                </div>
                <div class="form-group">
                    <label class="form-label">Description</label>
                    <textarea id="projectDescriptionInput" class="form-textarea" rows="3" placeholder="Project description (optional)"></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">Start Date</label>
                    <input type="date" id="projectStartDateInput" class="form-input">
                </div>
                <div class="form-group">
                    <label class="form-label">End Date</label>
                    <input type="date" id="projectEndDateInput" class="form-input">
                </div>
                <div class="form-group">
                    <label class="form-label">Status</label>
                    <select id="projectStatusSelect" class="form-select">
                        <option value="planning">Planning</option>
                        <option value="active" selected>Active</option>
                        <option value="on_hold">On Hold</option>
                        <option value="completed">Completed</option>
                        <option value="cancelled">Cancelled</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Initial Progress (%)</label>
                    <input type="number" id="projectProgressInput" class="form-input" value="0" min="0" max="100">
                </div>
                <div style="display: flex; gap: 1rem; margin-top: 1.5rem;">
                    <button id="projectDialogCancel" class="btn btn-secondary" style="flex:1;">Cancel</button>
                    <button id="projectDialogConfirm" class="btn btn-primary" style="flex:1;">Create Project</button>
                </div>
            `;

            document.body.appendChild(dialog);

            const cancelBtn = document.getElementById('projectDialogCancel');
            const confirmBtn = document.getElementById('projectDialogConfirm');

            if (cancelBtn) {
                cancelBtn.addEventListener('click', () => {
                    if (document.body.contains(dialog)) {
                        document.body.removeChild(dialog);
                    }
                });
            }

            if (confirmBtn) {
                confirmBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const name = document.getElementById('projectNameInput').value.trim();
                    const description = document.getElementById('projectDescriptionInput').value.trim();
                    const startDate = document.getElementById('projectStartDateInput').value;
                    const endDate = document.getElementById('projectEndDateInput').value;
                    const status = document.getElementById('projectStatusSelect').value;
                    const progress = parseInt(document.getElementById('projectProgressInput').value || '0', 10);

                    if (!name) {
                        alert('Project name is required');
                        return;
                    }

                    confirmBtn.disabled = true;
                    const originalText = confirmBtn.innerHTML;
                    confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

                    fetch('/teams/add-project/', {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrftoken,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            team_id: teamId,
                            name,
                            description,
                            start_date: startDate,
                            end_date: endDate,
                            status,
                            progress
                        })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            alert(data.message || 'Project created successfully');
                            if (document.body.contains(dialog)) {
                                document.body.removeChild(dialog);
                            }
                            // Refresh team details in modal
                            const manageBtn = document.querySelector(`.manage-team-btn[data-team-id="${teamId}"]`);
                            if (manageBtn) {
                                manageBtn.click();
                            } else {
                                location.reload();
                            }
                        } else {
                            alert('Error creating project: ' + (data.message || 'Unknown error'));
                            confirmBtn.disabled = false;
                            confirmBtn.innerHTML = originalText;
                        }
                    })
                    .catch(error => {
                        console.error('Error creating project:', error);
                        alert('Error creating project');
                        confirmBtn.disabled = false;
                        confirmBtn.innerHTML = originalText;
                    });
                });
            }
        });
    }

    // Attach delete handlers for teams
    document.querySelectorAll('.delete-team-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const teamId = this.getAttribute('data-team-id');
            const teamName = this.getAttribute('data-team-name');
            if (!teamId) return;

            if (!confirm(`Are you sure you want to delete team "${teamName}"? This action cannot be undone.`)) {
                return;
            }

            fetch(`/teams/${teamId}/delete/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(data.message || 'Team deleted successfully');
                    location.reload();
                } else {
                    alert('Error deleting team: ' + (data.message || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error deleting team:', error);
                alert('Error deleting team');
            });
        });
    });

    // Member Details Modal Logic
    const memberDetailsModal = document.getElementById('memberDetailsModal');
    const closeMemberModal = document.getElementById('closeMemberModal');
    const memberDetailsBody = document.getElementById('memberDetailsBody');
    const memberDetailsTitle = document.getElementById('memberDetailsTitle');

    // Function to show member details
    function showMemberDetails(memberId) {
        console.log('Showing details for member ID:', memberId);

        fetch(`/employees/${memberId}/details/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const member = data.member;
                memberDetailsTitle.textContent = `${member.name} - Details`;

                memberDetailsBody.innerHTML = `
                    <div style="margin: 1.5rem;">
                        <strong>Email:</strong> ${member.email || 'N/A'}<br>
                        <strong>Phone:</strong> ${member.phone || 'N/A'}<br>
                        <strong>Department:</strong> ${member.department || 'N/A'}<br>
                        <strong>Position:</strong> ${member.position || 'N/A'}<br>
                        <strong>Join Date:</strong> ${member.join_date || 'N/A'}<br>
                        <strong>Attendance:</strong> ${member.attendance_rate || 0}%<br>
                        <strong>Leaves Taken:</strong> ${member.leaves_taken || 0}<br>
                        <strong>Performance Rating:</strong> ${member.performance_rating || 'N/A'}/5
                    </div>
                    <h3 style="margin: 1.5rem 1.5rem 0.5rem;">Recent Attendance</h3>
                    <table class="table" style="margin: 1.5rem; width: calc(100% - 3rem); border-collapse: collapse;">
                        <thead>
                            <tr>
                                <th style="padding: 0.75rem; border-bottom: 1px solid var(--border-color); text-align: left;">Date</th>
                                <th style="padding: 0.75rem; border-bottom: 1px solid var(--border-color); text-align: left;">Status</th>
                                <th style="padding: 0.75rem; border-bottom: 1px solid var(--border-color); text-align: left;">Check-in</th>
                                <th style="padding: 0.75rem; border-bottom: 1px solid var(--border-color); text-align: left;">Check-out</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${(member.attendance_records && member.attendance_records.length > 0) ?
                                member.attendance_records.map(record => `
                                <tr>
                                    <td style="padding: 0.75rem; border-bottom: 1px solid var(--border-color);">${record.date || 'N/A'}</td>
                                    <td style="padding: 0.75rem; border-bottom: 1px solid var(--border-color);">${record.status || 'N/A'}</td>
                                    <td style="padding: 0.75rem; border-bottom: 1px solid var(--border-color);">${record.check_in || '-'}</td>
                                    <td style="padding: 0.75rem; border-bottom: 1px solid var(--border-color);">${record.check_out || '-'}</td>
                                </tr>
                                `).join('') :
                                '<tr><td colspan="4" style="padding: 0.75rem; text-align: center;">No attendance records found</td></tr>'
                            }
                        </tbody>
                    </table>
                    <div style="display: flex; gap: 1rem; margin: 1.5rem;">
                        <a href="/attendance/?employee_id=${memberId}" class="btn btn-secondary" style="flex:1;text-align:center;" target="_blank">
                            <i class="fas fa-calendar-alt"></i> View Full Attendance
                        </a>
                        <button class="btn btn-primary" id="viewMonthReportBtn" style="flex:1;text-align:center;">
                            <i class="fas fa-chart-line"></i> Month Report
                        </button>
                    </div>
                `;

                memberDetailsModal.classList.add('active');

                // Month report button logic
                setTimeout(() => {
                    const monthBtn = document.getElementById('viewMonthReportBtn');
                    if (monthBtn) {
                        monthBtn.onclick = function() {
                            window.open(`/reports/employee/${memberId}/monthly/`, '_blank');
                        };
                    }
                }, 100);
            } else {
                alert('Error loading member details: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error loading member details');
        });
    }

    // Show member details when clicking "eye" button
    document.querySelectorAll('.view-member-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const memberId = this.getAttribute('data-member-id');
            showMemberDetails(memberId);
        });
    });

    // Function to remove team member
    function removeTeamMember(teamId, memberId) {
        if (confirm('Are you sure you want to remove this member from the team?')) {
            fetch('/teams/remove-member/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    team_id: teamId,
                    member_id: memberId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Member removed successfully!');
                    // Refresh the team management modal
                    const manageBtn = document.querySelector(`.manage-team-btn[data-team-id="${teamId}"]`);
                    if (manageBtn) {
                        manageBtn.click();
                    }
                } else {
                    alert('Error removing member: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error removing member');
            });
        }
    }

    // Close member details modal
    if (closeMemberModal && memberDetailsModal) {
        closeMemberModal.addEventListener('click', () => {
            memberDetailsModal.classList.remove('active');
        });
    }

    if (memberDetailsModal) {
        memberDetailsModal.addEventListener('click', (e) => {
            if (e.target === memberDetailsModal) {
                memberDetailsModal.classList.remove('active');
            }
        });
    }

    // Helper function to get CSRF token from cookie
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Function to load attendance for all teams
    function loadAllTeamsAttendance() {
        // Get all team cards
        const teamCards = document.querySelectorAll('.team-card');

        teamCards.forEach(card => {
            const teamMembersList = card.querySelector('.team-members-list');
            if (!teamMembersList) return;

            const teamId = teamMembersList.getAttribute('data-team-id');
            if (!teamId) return;

            // Load attendance for this team
            loadTeamAttendance(teamId);
        });
    }

    // Function to load attendance for a specific team
    function loadTeamAttendance(teamId) {
        const csrfToken = getCookie('csrftoken') || csrftoken;

        fetch(`/teams/${teamId}/attendance/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': csrfToken || '',
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.members) {
                // Update attendance for each member (both in team cards and modal)
                data.members.forEach(member => {
                    const att = member.attendance;
                    const isPresent = att.is_present;
                    const statusClass = isPresent ? 'present' : 'absent';
                    const iconClass = isPresent ? 'fa-check-circle' : 'fa-times-circle';

                    let html = `<span class="attendance-badge ${statusClass}">`;
                    html += `<i class="fas ${iconClass}"></i> `;
                    html += att.status_display;
                    html += `</span>`;

                    if (att.check_in) {
                        html += ` <span class="attendance-time">${att.check_in}</span>`;
                    }

                    // Update in team card
                    const attendanceElement = document.getElementById(`attendance-${member.id}`);
                    if (attendanceElement) {
                        attendanceElement.innerHTML = html;
                    }

                    // Update in modal
                    const modalAttendanceElement = document.getElementById(`modal-attendance-${member.id}`);
                    if (modalAttendanceElement) {
                        modalAttendanceElement.innerHTML = html;
                    }
                });
            }
        })
        .catch(error => {
            console.error('Error loading attendance:', error);
            // Show error state
            document.querySelectorAll(`[id^="attendance-"], [id^="modal-attendance-"]`).forEach(el => {
                if (el && el.innerHTML.includes('Loading')) {
                    el.innerHTML = '<span class="attendance-badge absent"><i class="fas fa-exclamation-circle"></i> Error</span>';
                }
            });
        });
    }

    // Load attendance for all teams on page load
    loadAllTeamsAttendance();

    // Auto-refresh attendance every 5 minutes
    setInterval(() => {
        loadAllTeamsAttendance();
    }, 5 * 60 * 1000); // 5 minutes
});