/**
 * EmployeeView.js — DOM rendering layer for Employees (MVC View)
 */

import { BaseView } from '../core/BaseView.js';

export class EmployeeView extends BaseView {
    constructor() {
        super();
        this.form              = document.getElementById('employeeForm');
        this.tabs              = document.querySelectorAll('.tab');
        this.tabContents       = document.querySelectorAll('.tab-content');
        this.photoUpload       = document.getElementById('photoUpload');
        this.employeePhoto     = document.getElementById('employeePhoto');
        this.cancelBtn         = document.getElementById('cancelBtn');
        this.additionalContainer = document.getElementById('additionalDocumentsContainer');
        this.addAdditionalBtn    = document.getElementById('addAdditionalDocumentBtn');
        this._additionalCounter  = 0;
    }

    // ── Tab navigation ──────────────────────────
    activateTab(tabId) {
        this.tabs.forEach(t => t.classList.remove('active'));
        this.tabContents.forEach(c => c.classList.remove('active'));
        const tab     = document.querySelector(`.tab[data-tab="${tabId}"]`);
        const content = document.getElementById(`${tabId}Tab`);
        if (tab)     tab.classList.add('active');
        if (content) content.classList.add('active');
    }

    bindTabClicks(onTabClick) {
        this.tabs.forEach(tab =>
            tab.addEventListener('click', () => onTabClick(tab.getAttribute('data-tab')))
        );
    }

    bindNextButtons(onNext) {
        document.querySelectorAll('.next-tab-btn').forEach(btn =>
            btn.addEventListener('click', function () {
                onNext(this.getAttribute('data-next'), this.closest('.tab-content'));
            })
        );
    }

    bindPrevButtons(onPrev) {
        document.querySelectorAll('.prev-tab-btn').forEach(btn =>
            btn.addEventListener('click', function () {
                onPrev(this.getAttribute('data-prev'));
            })
        );
    }

    validateTabFields(tabContentEl) {
        let allValid = true;
        tabContentEl.querySelectorAll('[required]').forEach(field => {
            if (!field.value.trim()) { allValid = false; field.classList.add('error'); }
            else field.classList.remove('error');
        });
        return allValid;
    }

    // ── Photo upload ────────────────────────────
    bindPhotoUpload() {
        if (!this.photoUpload || !this.employeePhoto) return;
        this.employeePhoto.addEventListener('click', () => {
            if (!this.photoUpload.disabled) this.photoUpload.click();
        });
        this.photoUpload.addEventListener('change', () => {
            const file = this.photoUpload.files[0];
            if (!file) return;
            const allowed = ['image/jpeg','image/jpg','image/png','image/gif'];
            if (!allowed.includes(file.type)) {
                this.showNotification('Please upload a valid image file (JPG, PNG, GIF)', 'error');
                this.photoUpload.value = ''; return;
            }
            if (file.size > 5 * 1024 * 1024) {
                this.showNotification('File size must be less than 5 MB', 'error');
                this.photoUpload.value = ''; return;
            }
            const reader = new FileReader();
            reader.onload = e => { this.employeePhoto.src = e.target.result; };
            reader.readAsDataURL(file);
        });
    }

    // ── Document uploads ────────────────────────
    bindDocumentUploads(docSlots) {
        docSlots.forEach(doc =>
            this._bindUploadHandler(document.querySelector(doc.input), doc.name)
        );
    }

    _bindUploadHandler(inputEl, docNameProvider) {
        if (!inputEl) return;
        inputEl.addEventListener('change', () => {
            const file = inputEl.files[0];
            if (!file) { this._resetUploadLabel(inputEl); return; }
            if (file.size > 10 * 1024 * 1024) {
                this.showNotification('File size must be less than 10 MB', 'error');
                inputEl.value = ''; this._resetUploadLabel(inputEl); return;
            }
            this._setUploadLabel(inputEl.nextElementSibling, file.name);
            const name = typeof docNameProvider === 'function' ? docNameProvider() : docNameProvider;
            this._addToDocumentList(name || 'Document', file.name);
        });
        const labelEl = inputEl.nextElementSibling;
        if (labelEl) {
            labelEl.addEventListener('click', e => {
                if (e.target.closest('.clear-upload-btn')) {
                    e.preventDefault(); e.stopPropagation();
                    inputEl.value = ''; this._resetUploadLabel(inputEl);
                }
            });
        }
    }

    _setUploadLabel(labelEl, fileName) {
        if (!labelEl) return;
        const date = new Date().toLocaleDateString();
        labelEl.innerHTML = `
            <div class="file-upload-selected">
                <div class="file-upload-selected-main">
                    <span class="file-icon"><i class="fas fa-check-circle"></i></span>
                    <span class="file-meta">
                        <span class="file-name">${fileName}</span>
                        <span class="upload-date">Selected on ${date}</span>
                    </span>
                </div>
                <button type="button" class="clear-upload-btn" aria-label="Clear file">
                    <i class="fas fa-times"></i>
                </button>
            </div>`;
        labelEl.style.color = '#047857';
        labelEl.style.borderColor = '#10b981';
        labelEl.style.background = '#ecfdf5';
    }

    _resetUploadLabel(inputEl) {
        const labelEl = inputEl?.nextElementSibling;
        if (!labelEl) return;
        const def = labelEl.getAttribute('data-default-label') || 'Upload File';
        labelEl.innerHTML = `<i class="fas fa-upload"></i> ${def}`;
        labelEl.style.color = labelEl.style.borderColor = labelEl.style.background = '';
    }

    _addToDocumentList(docType, fileName) {
        const list = document.querySelector('.document-list');
        if (!list) return;
        const item = document.createElement('div');
        item.className = 'document-item';
        item.innerHTML = `
            <div class="document-info">
                <div class="document-icon"><i class="fas fa-file-alt"></i></div>
                <div>
                    <div style="font-weight:600;">${fileName}</div>
                    <div style="font-size:0.8rem;color:var(--text-light);">
                        ${docType} - Uploaded on ${new Date().toLocaleDateString()}
                    </div>
                </div>
            </div>
            <div class="document-actions">
                <button type="button" class="btn btn-sm btn-danger"
                        onclick="this.parentElement.parentElement.remove()">
                    <i class="fas fa-trash"></i>
                </button>
            </div>`;
        list.appendChild(item);
    }

    // ── Additional document slots ───────────────
    bindAddAdditionalDocument() {
        if (this.addAdditionalBtn && this.additionalContainer) {
            this.addAdditionalBtn.addEventListener('click', () => this._createAdditionalSlot());
        }
    }

    _createAdditionalSlot() {
        this._additionalCounter++;
        const n = this._additionalCounter;
        const slotId = `additionalUpload${n}`;
        const wrapper = document.createElement('div');
        wrapper.className = 'additional-upload';
        wrapper.innerHTML = `
            <input type="text" class="form-input" name="additional_document_label_${n}"
                   placeholder="Document title (e.g., Reference Letter)">
            <div class="file-upload">
                <input type="file" class="file-upload-input" id="${slotId}"
                       name="additional_document_file_${n}" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx">
                <label for="${slotId}" class="file-upload-label">
                    <i class="fas fa-upload"></i> Upload file
                </label>
            </div>
            <button type="button" class="remove-upload" aria-label="Remove">&times;</button>`;
        wrapper.querySelector('.remove-upload').addEventListener('click', () => wrapper.remove());
        this._bindUploadHandler(wrapper.querySelector('.file-upload-input'), () =>
            wrapper.querySelector('.form-input')?.value?.trim() || 'Additional Document'
        );
        this.additionalContainer.appendChild(wrapper);
    }

    // ── Form helpers ────────────────────────────
    reenableDisabledFields() {
        if (!this.form) return;
        this.form.querySelectorAll('input:disabled,select:disabled,textarea:disabled').forEach(f => {
            if (!['file','submit','button'].includes(f.type)) f.disabled = false;
        });
    }

    setSubmitLoading(isLoading) {
        document.querySelectorAll('.save-employee-btn').forEach(btn =>
            this.setButtonLoading(btn, isLoading, 'Saving...')
        );
    }

    resetForm() {
        this.form?.reset();
        if (this.employeePhoto) this.employeePhoto.src = 'https://via.placeholder.com/120';
        document.querySelectorAll('.file-upload-label').forEach(lbl =>
            this._resetUploadLabel(lbl.previousElementSibling)
        );
        const docList = document.querySelector('.document-list');
        if (docList) docList.innerHTML = '';
        if (this.additionalContainer) this.additionalContainer.innerHTML = '';
        const firstTab = this.tabs[0]?.getAttribute('data-tab');
        if (firstTab) this.activateTab(firstTab);
    }
}
