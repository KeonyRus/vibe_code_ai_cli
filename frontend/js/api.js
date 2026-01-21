/**
 * API client for Airganizator
 */
const API = {
    baseUrl: '/api',

    // Projects
    async getProjects() {
        const res = await fetch(`${this.baseUrl}/projects/`);
        return res.json();
    },

    async getProject(id) {
        const res = await fetch(`${this.baseUrl}/projects/${id}`);
        return res.json();
    },

    async createProject(data) {
        const res = await fetch(`${this.baseUrl}/projects/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    },

    async updateProject(id, data) {
        const res = await fetch(`${this.baseUrl}/projects/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    },

    async deleteProject(id) {
        const res = await fetch(`${this.baseUrl}/projects/${id}`, {
            method: 'DELETE'
        });
        return res.json();
    },

    async startProject(id) {
        const res = await fetch(`${this.baseUrl}/projects/${id}/start`, {
            method: 'POST'
        });
        return res.json();
    },

    async stopProject(id) {
        const res = await fetch(`${this.baseUrl}/projects/${id}/stop`, {
            method: 'POST'
        });
        return res.json();
    },

    async changeMode(id, mode) {
        const res = await fetch(`${this.baseUrl}/projects/${id}/mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode })
        });
        return res.json();
    },

    // Settings
    async getSettings() {
        const res = await fetch(`${this.baseUrl}/settings/`);
        return res.json();
    },

    async updateSettings(data) {
        const res = await fetch(`${this.baseUrl}/settings/`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    },

    async updateApiKeys(data) {
        const res = await fetch(`${this.baseUrl}/settings/api-keys`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    },

    // .env
    async getEnv(projectId) {
        const res = await fetch(`${this.baseUrl}/env/${projectId}`);
        return res.json();
    },

    async updateEnv(projectId, content) {
        const res = await fetch(`${this.baseUrl}/env/${projectId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });
        return res.json();
    },

    // Zeusovich
    async getZeusovichStatus() {
        const res = await fetch(`${this.baseUrl}/zeusovich/status`);
        return res.json();
    },

};
