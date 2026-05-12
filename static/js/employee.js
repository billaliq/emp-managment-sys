// Splash Screen Logic - Now handled by splash.js for consistency
document.addEventListener('DOMContentLoaded', function() {
    const splashScreen = document.getElementById('splashScreen');
    if (splashScreen && !window.splashScreenHandled) {
        splashScreen.style.display = 'flex';
        setTimeout(function() {
            splashScreen.style.opacity = '0';
            setTimeout(function() {
                splashScreen.style.display = 'none';
            }, 400);
        }, 2000); // Display time: 2 seconds
    }

    // Tab functionality
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.getAttribute('data-tab');
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`${tabId}Tab`).classList.add('active');
        });
    });

    // ✅ Next button functionality with validation
    const nextButtons = document.querySelectorAll('.next-tab-btn');
    nextButtons.forEach(button => {
        button.addEventListener('click', function () {
            const nextTabId = this.getAttribute('data-next');
            const currentTabContent = this.closest('.tab-content');

            // Validate required fields inside current tab
            const requiredFields = currentTabContent.querySelectorAll('[required]');
            let allValid = true;

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    allValid = false;
                    field.classList.add("error"); // optional: style invalid fields
                } else {
                    field.classList.remove("error");
                }
            });

            if (!allValid) {
                alert("⚠️ Please fill the required fields before continuing.");
                return;
            }

            // Switch tab if valid
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            document.getElementById(nextTabId).classList.add('active');

            const nextTab = document.querySelector(`.tab[data-tab="${nextTabId.replace("Tab", "")}"]`);
            if (nextTab) nextTab.classList.add('active');
        });
    });

    // ✅ Previous button functionality
    const prevButtons = document.querySelectorAll('.prev-tab-btn');
    prevButtons.forEach(button => {
        button.addEventListener('click', function () {
            const prevTabId = this.getAttribute('data-prev');

            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            document.getElementById(prevTabId).classList.add('active');

            const prevTab = document.querySelector(`.tab[data-tab="${prevTabId.replace("Tab", "")}"]`);
            if (prevTab) prevTab.classList.add('active');
        });
    });

    // ✅ Employee Form Submission - MODIFIED TO SUBMIT TO BACKEND
    const employeeForm = document.getElementById('employeeForm');
    if (employeeForm) {
        employeeForm.addEventListener('submit', function(e) {
            // Check if this is an update (employee_id exists) or new creation
            const employeeIdHidden = employeeForm.querySelector('input[name="employee_id"]');
            const isUpdate = employeeIdHidden && employeeIdHidden.value.trim();

            // For new employees, require code field. For updates, employee_id is sufficient.
            if (!isUpdate) {
                const employeeIdField = employeeForm.querySelector('input[name="code"]');
                const employeeIdDisplay = document.getElementById('employeeCodeDisplay');

                // Get employee ID from hidden field or display field
                let employeeId = '';
                if (employeeIdField) {
                    employeeId = employeeIdField.value.trim();
                } else if (employeeIdDisplay) {
                    employeeId = employeeIdDisplay.value.trim();
                }

                if (!employeeId) {
                    e.preventDefault();
                    alert('No employee ID is given. Please ensure the employee ID is available before submitting.');
                    return false;
                }
            }

            // Re-enable disabled fields before submission so their values are included
            const disabledFields = employeeForm.querySelectorAll('input:disabled, select:disabled, textarea:disabled');
            const disabledFieldValues = [];
            disabledFields.forEach(field => {
                if (field.type !== 'file' && field.type !== 'submit' && field.type !== 'button') {
                    disabledFieldValues.push({
                        field: field,
                        wasDisabled: true
                    });
                    field.disabled = false;
                }
            });

            // Show loading state
            const submitButtons = document.querySelectorAll('.save-employee-btn');
            submitButtons.forEach(btn => {
                if (!btn.disabled) {
                    btn.disabled = true;
                    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
                }
            });

            // IMPORTANT: Don't call e.preventDefault() - let the form submit naturally
            // The form will POST to the Django backend
            // Explicitly allow the form to submit
        }, false); // Use bubble phase (default)

        // Ensure submit button works - add direct click handler as fallback
        const submitButtons = document.querySelectorAll('.save-employee-btn');
        submitButtons.forEach(btn => {
            btn.addEventListener('click', function(e) {
                // If button is already disabled, don't do anything
                if (this.disabled) {
                    e.preventDefault();
                    return false;
                }
                // The form's submit event handler will handle validation and submission
                // Don't prevent default - let the button's default behavior trigger form submit
            });
        });
    }

    // ✅ Photo upload preview
    const photoUpload = document.getElementById('photoUpload');
    const employeePhoto = document.getElementById('employeePhoto');
    const employeeCodeHidden = document.querySelector('#employeeForm input[name="code"]');
    const employeeCodeDisplay = document.getElementById('employeeCodeDisplay');

    // Sync hidden employee code to visible read-only field (for existing/assigned IDs)
    if (employeeCodeHidden && employeeCodeDisplay && employeeCodeHidden.value && !employeeCodeDisplay.value) {
        employeeCodeDisplay.value = employeeCodeHidden.value;
    }
    if (photoUpload && employeePhoto) {
        // Make photo image clickable to trigger file input
        employeePhoto.addEventListener('click', function(e) {
            // Only trigger if the file input is not disabled
            if (!photoUpload.disabled) {
                photoUpload.click();
            }
        });

        photoUpload.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                // Validate file type
                const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif'];
                if (!allowedTypes.includes(file.type)) {
                    alert('Please upload a valid image file (JPG, PNG, GIF)');
                    this.value = '';
                    return;
                }

                // Validate file size (5MB max)
                if (file.size > 5 * 1024 * 1024) {
                    alert('File size must be less than 5MB');
                    this.value = '';
                    return;
                }

                const reader = new FileReader();
                reader.onload = function(e) {
                    employeePhoto.src = e.target.result;
                }
                reader.readAsDataURL(file);
            }
        });
    }

    // ✅ Document upload functionality (shows upload date)
    const documentUploads = [
        { input: '#cnicUpload', name: 'CNIC Copy' },
        { input: '#passportUpload', name: 'Passport Size Photo' },
        { input: '#resumeUpload', name: 'Updated Resume' },
        { input: '#eduUpload', name: 'Educational Certificate' },
        { input: '#expUpload', name: 'Experience Letter' },
        { input: '#offerUpload', name: 'Signed Offer Letter' },
        { input: '#ndaUpload', name: 'Signed NDA Form' }
    ];

    function setUploadLabel(labelEl, fileName) {
        if (!labelEl) return;
        const dateText = new Date().toLocaleDateString();
        labelEl.innerHTML = `
            <div class="file-upload-selected">
                <div class="file-upload-selected-main">
                    <span class="file-icon"><i class="fas fa-check-circle"></i></span>
                    <span class="file-meta">
                        <span class="file-name">${fileName}</span>
                        <span class="upload-date">Selected on ${dateText}</span>
                    </span>
                </div>
                <button type="button" class="clear-upload-btn" aria-label="Clear file">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        labelEl.style.color = '#047857';
        labelEl.style.borderColor = '#10b981';
        labelEl.style.background = '#ecfdf5';
    }

    function resetUploadLabel(inputEl) {
        if (!inputEl) return;
        const labelEl = inputEl.nextElementSibling;
        if (!labelEl) return;
        const defaultText = labelEl.getAttribute('data-default-label') || 'Upload File';
        labelEl.innerHTML = `<i class="fas fa-upload"></i> ${defaultText}`;
        labelEl.style.color = '';
        labelEl.style.borderColor = '';
        labelEl.style.background = '';
    }

    function bindUploadHandler(inputEl, docNameProvider) {
        if (!inputEl) return;

        inputEl.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                if (file.size > 10 * 1024 * 1024) {
                    alert('File size must be less than 10MB');
                    this.value = '';
                    resetUploadLabel(this);
                    return;
                }
                setUploadLabel(this.nextElementSibling, file.name);
                const docName = typeof docNameProvider === 'function' ? docNameProvider() : docNameProvider;
                addToDocumentList(docName || 'Document', file.name);
            } else {
                resetUploadLabel(this);
            }
        });

        // Delegate clear button click to the label
        const labelEl = inputEl.nextElementSibling;
        if (labelEl) {
            labelEl.addEventListener('click', function(e) {
                const clearBtn = e.target.closest('.clear-upload-btn');
                if (clearBtn) {
                    e.preventDefault();
                    e.stopPropagation();
                    inputEl.value = '';
                    resetUploadLabel(inputEl);
                }
            });
        }
    }

    documentUploads.forEach(doc => {
        bindUploadHandler(document.querySelector(doc.input), doc.name);
    });

    // ✅ Function to add document to the list
    function addToDocumentList(docType, fileName) {
        const documentList = document.querySelector('.document-list');
        if (documentList) {
            const documentItem = document.createElement('div');
            documentItem.className = 'document-item';
            documentItem.innerHTML = `
                <div class="document-info">
                    <div class="document-icon">
                        <i class="fas fa-file-alt"></i>
                    </div>
                    <div>
                        <div style="font-weight: 600;">${fileName}</div>
                        <div style="font-size: 0.8rem; color: var(--text-light);">${docType} - Uploaded on ${new Date().toLocaleDateString()}</div>
                    </div>
                </div>
                <div class="document-actions">
                    <button type="button" class="btn btn-sm btn-danger" onclick="this.parentElement.parentElement.remove()">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            documentList.appendChild(documentItem);
        }
    }

    // ✅ Additional documents (dynamic slots)
    const additionalContainer = document.getElementById('additionalDocumentsContainer');
    const addAdditionalBtn = document.getElementById('addAdditionalDocumentBtn');
    let additionalCounter = 0;

    function createAdditionalUploadSlot() {
        additionalCounter += 1;
        const slotId = `additionalUpload${additionalCounter}`;

        const wrapper = document.createElement('div');
        wrapper.className = 'additional-upload';
        wrapper.innerHTML = `
            <input type="text" class="form-input" name="additional_document_label_${additionalCounter}" placeholder="Document title (e.g., Reference Letter)">
            <div class="file-upload">
                <input type="file" class="file-upload-input" id="${slotId}" name="additional_document_file_${additionalCounter}" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx">
                <label for="${slotId}" class="file-upload-label"><i class="fas fa-upload"></i> Upload file</label>
            </div>
            <button type="button" class="remove-upload" aria-label="Remove document slot">&times;</button>
        `;

        const removeBtn = wrapper.querySelector('.remove-upload');
        removeBtn.addEventListener('click', () => wrapper.remove());

        const uploadInput = wrapper.querySelector('.file-upload-input');
        bindUploadHandler(uploadInput, () => {
            const nameInput = wrapper.querySelector('.form-input');
            return nameInput?.value?.trim() || 'Additional Document';
        });

        additionalContainer.appendChild(wrapper);
    }

    if (addAdditionalBtn && additionalContainer) {
        addAdditionalBtn.addEventListener('click', () => {
            createAdditionalUploadSlot();
        });
    }

    // ✅ Cancel button functionality
    const cancelBtn = document.getElementById('cancelBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to cancel? All unsaved changes will be lost.')) {
                // Reset form
                employeeForm.reset();

                // Reset photo preview
                if (employeePhoto) {
                    employeePhoto.src = 'https://via.placeholder.com/120';
                }

                // Reset file upload labels
                document.querySelectorAll('.file-upload-label').forEach(label => {
                    const icon = label.querySelector('i').className;
                    const text = label.textContent.includes('Upload') ? label.textContent : 'Upload File';
                    label.innerHTML = `<i class="${icon}"></i> ${text}`;
                    label.style.color = '';
                    label.style.borderColor = '';
                });

                // Clear document list
                const documentList = document.querySelector('.document-list');
                if (documentList) {
                    documentList.innerHTML = '';
                }
                const additionalDocs = document.getElementById('additionalDocumentsContainer');
                if (additionalDocs) {
                    additionalDocs.innerHTML = '';
                }

                // Go back to first tab
                tabs.forEach(t => t.classList.remove('active'));
                tabContents.forEach(c => c.classList.remove('active'));
                tabs[0].classList.add('active');
                tabContents[0].classList.add('active');
            }
        });
    }

    // ✅ Load existing employees if editing
    function loadEmployeeData(employeeId) {
        // This function would need to be adapted to fetch data from your backend
    }

    // Check if we're editing an existing employee (based on URL parameters)
    const urlParams = new URLSearchParams(window.location.search);
    const editEmployeeId = urlParams.get('edit');
    if (editEmployeeId) {
        loadEmployeeData(editEmployeeId);
    }

    // ✅ Show Django messages as popups
    const djangoMessages = document.querySelectorAll('.messages .alert');
    if (djangoMessages.length > 0) {
        djangoMessages.forEach(msg => {
            alert(msg.innerText); // native popup
        });
    }
});
