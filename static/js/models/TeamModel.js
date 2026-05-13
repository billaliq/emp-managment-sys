/**
 * TeamModel.js — Data access layer for Teams (MVC Model)
 */

import { BaseModel } from '../core/BaseModel.js';

export class TeamModel extends BaseModel {
    constructor() {
        super('/teams');
    }

    /**
     * Fetch full details of a single team (members, projects, leader).
     * @param {string|number} id
     */
    async getById(id) {
        return this.get(`/${id}/details/`);
    }

    /**
     * Create a new team.
     * @param {FormData} formData
     */
    async create(formData) {
        return this.post('/create/', formData);
    }

    /**
     * Update team settings.
     * @param {Object} data  { team_id, team_name, team_lead, department, status }
     */
    async update(data) {
        return this.postJson('/update/', data);
    }

    /**
     * Delete a team.
     * @param {string|number} id
     */
    async delete(id) {
        return this.postJson(`/${id}/delete/`, {});
    }

    /**
     * Add members to a team.
     * @param {string|number} teamId
     * @param {number[]} memberIds
     */
    async addMembers(teamId, memberIds) {
        return this.postJson('/add-members/', { team_id: parseInt(teamId), member_ids: memberIds });
    }

    /**
     * Remove a member from a team.
     * @param {string|number} teamId
     * @param {string|number} memberId
     */
    async removeMember(teamId, memberId) {
        return this.postJson('/remove-member/', { team_id: parseInt(teamId), member_id: parseInt(memberId) });
    }

    /**
     * Add a project to a team.
     * @param {Object} projectData
     */
    async addProject(projectData) {
        return this.postJson('/add-project/', projectData);
    }

    /**
     * Fetch today's attendance for team members.
     * @param {string|number} teamId
     */
    async getAttendance(teamId) {
        return this.get(`/${teamId}/attendance/`);
    }
}
