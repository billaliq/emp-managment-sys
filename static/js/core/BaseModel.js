/**
 * BaseModel.js — Abstract base class for all MVC Models (MVC Core)
 *
 * Responsibilities:
 *  - All HTTP communication (GET, POST)
 *  - CSRF token management
 *  - Consistent error handling
 *  - No DOM knowledge whatsoever
 */

import { getCsrfToken } from './Utils.js';

export class BaseModel {
    /**
     * @param {string} baseUrl  e.g. '/departments'
     */
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    /**
     * Build a full URL from a path (relative to baseUrl) and optional query params.
     * @param {string} path
     * @param {Object|URLSearchParams} [params]
     * @returns {string}
     */
    _buildUrl(path = '', params = null) {
        const url = path.startsWith('http') ? path : `${this.baseUrl}${path}`;
        if (!params) return url;
        const qs = params instanceof URLSearchParams
            ? params.toString()
            : new URLSearchParams(params).toString();
        return qs ? `${url}?${qs}` : url;
    }

    /**
     * Perform a GET request.
     * @param {string} path           URL path appended to baseUrl
     * @param {Object} [params]       Query string parameters
     * @param {boolean} [isAjax=true] Adds X-Requested-With header
     * @returns {Promise<any>}        Parsed JSON response
     */
    async get(path = '', params = null, isAjax = true) {
        const url = this._buildUrl(path, params);
        const headers = { 'X-CSRFToken': getCsrfToken() };
        if (isAjax) headers['X-Requested-With'] = 'XMLHttpRequest';

        const res = await fetch(url, { method: 'GET', headers });
        return this._handleResponse(res);
    }

    /**
     * Perform a POST request with FormData.
     * @param {string} path
     * @param {FormData} formData
     * @returns {Promise<any>}
     */
    async post(path = '', formData) {
        const url = this._buildUrl(path);
        const res = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
        });
        return this._handleResponse(res);
    }

    /**
     * Perform a POST request with a JSON body.
     * @param {string} path
     * @param {Object} data
     * @returns {Promise<any>}
     */
    async postJson(path = '', data = {}) {
        const url = this._buildUrl(path);
        const res = await fetch(url, {
            method: 'POST',
            body: JSON.stringify(data),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
        });
        return this._handleResponse(res);
    }

    /**
     * Parse and validate an HTTP response.
     * Throws a descriptive Error on non-2xx or non-JSON responses.
     * @param {Response} res
     * @returns {Promise<any>}
     */
    async _handleResponse(res) {
        const contentType = res.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            const text = await res.text();
            throw new Error(`Unexpected response (${res.status}): ${text.slice(0, 200)}`);
        }
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || data.message || `Request failed (${res.status})`);
        }
        return data;
    }
}
