// Login Page JavaScript

document.addEventListener('DOMContentLoaded', function () {
    // Initialize login functionality
    initializeLogin();
    initializeAnimations();
    initializeFormValidation();
});

// Initialize login functionality
function initializeLogin() {
    const loginForm = document.querySelector('.login-form');
    const loginBtn = document.getElementById('loginBtn');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const btnLoader = document.getElementById('btnLoader');
    const btnText = document.querySelector('.btn-text');

    if (loginForm) {
        loginForm.addEventListener('submit', function (e) {
            e.preventDefault();
            handleLogin();
        });
    }

    // Handle login submission
    function handleLogin() {
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        if (!username || !password) {
            showMessage('Please fill in all fields', 'error');
            return;
        }

        // Show loading state
        showLoading(true);

        // Disable form
        loginBtn.disabled = true;
        btnText.style.opacity = '0';
        btnLoader.style.display = 'block';

        // Simulate login process (replace with actual AJAX call)
        setTimeout(() => {
            // Submit the form
            loginForm.submit();
        }, 1000);
    }

    // Show loading state
    function showLoading(show) {
        if (show) {
            loadingOverlay.classList.add('active');
        } else {
            loadingOverlay.classList.remove('active');
        }
    }
}

// Initialize animations
function initializeAnimations() {
    // Add entrance animations to elements
    const animatedElements = document.querySelectorAll('.login-card, .login-features');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animationPlayState = 'running';
            }
        });
    });

    animatedElements.forEach(el => {
        observer.observe(el);
    });

    // Add hover effects to feature items
    const featureItems = document.querySelectorAll('.feature-item');
    featureItems.forEach(item => {
        item.addEventListener('mouseenter', function () {
            this.style.transform = 'translateX(-10px) scale(1.02)';
        });

        item.addEventListener('mouseleave', function () {
            this.style.transform = 'translateX(0) scale(1)';
        });
    });
}

// Initialize form validation
function initializeFormValidation() {
    const inputs = document.querySelectorAll('.form-input');

    inputs.forEach(input => {
        // Add focus/blur effects
        input.addEventListener('focus', function () {
            this.parentElement.classList.add('focused');
        });

        input.addEventListener('blur', function () {
            this.parentElement.classList.remove('focused');
            validateInput(input);
        });

        // Real-time validation
        input.addEventListener('input', function () {
            clearTimeout(this.validationTimeout);
            this.validationTimeout = setTimeout(() => {
                validateInput(this);
            }, 300);
        });
    });
}

// Validate individual input
function validateInput(input) {
    const value = input.value.trim();
    const inputType = input.type;
    const inputName = input.name;

    // Remove existing validation classes
    input.classList.remove('valid', 'invalid');

    if (!value) {
        return; // Don't show error for empty fields
    }

    let isValid = true;
    let errorMessage = '';

    if (inputName === 'username') {
        isValid = value.length >= 3;
        errorMessage = 'Username must be at least 3 characters';
    } else if (inputType === 'email' && inputName === 'username') {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        isValid = emailRegex.test(value);
        errorMessage = 'Please enter a valid email address';
    } else if (inputName === 'password') {
        isValid = value.length >= 6;
        errorMessage = 'Password must be at least 6 characters';
    }

    if (isValid) {
        input.classList.add('valid');
        removeErrorMessage(input);
    } else {
        input.classList.add('invalid');
        showErrorMessage(input, errorMessage);
    }
}

// Show error message
function showErrorMessage(input, message) {
    removeErrorMessage(input);

    const errorDiv = document.createElement('div');
    errorDiv.className = 'input-error';
    errorDiv.textContent = message;

    // Find the parent form-group to append error message
    // This prevents the error from messing up the input-group flex layout
    const formGroup = input.closest('.form-group');
    if (formGroup) {
        formGroup.appendChild(errorDiv);
    } else {
        // Fallback if structure is different
        input.parentElement.appendChild(errorDiv);
    }
}

// Remove error message
function removeErrorMessage(input) {
    const formGroup = input.closest('.form-group');
    if (formGroup) {
        const existingError = formGroup.querySelector('.input-error');
        if (existingError) {
            existingError.remove();
        }
    }
}

// Toggle password visibility
function togglePassword() {
    const passwordInput = document.getElementById('password');
    const toggleIcon = document.getElementById('passwordToggleIcon');

    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleIcon.classList.remove('fa-eye');
        toggleIcon.classList.add('fa-eye-slash');
    } else {
        passwordInput.type = 'password';
        toggleIcon.classList.remove('fa-eye-slash');
        toggleIcon.classList.add('fa-eye');
    }
}

// Show message (for notifications)
function showMessage(message, type = 'info') {
    // Remove existing messages
    const existingMessages = document.querySelectorAll('.login-messages .alert');
    existingMessages.forEach(msg => msg.remove());

    // Create new message
    const messageDiv = document.createElement('div');
    messageDiv.className = `alert alert-${type}`;

    const iconClass = type === 'error' ? 'exclamation-circle' :
        type === 'success' ? 'check-circle' : 'info-circle';

    messageDiv.innerHTML = `
        <i class="fas fa-${iconClass}"></i>
        ${message}
    `;

    // Add to messages container
    let messagesContainer = document.querySelector('.login-messages');
    if (!messagesContainer) {
        messagesContainer = document.createElement('div');
        messagesContainer.className = 'login-messages';
        const form = document.querySelector('.login-form');
        form.insertBefore(messagesContainer, form.firstChild);
    }

    messagesContainer.appendChild(messageDiv);

    // Auto remove after 5 seconds
    setTimeout(() => {
        if (messageDiv.parentElement) {
            messageDiv.remove();
        }
    }, 5000);
}

// Add keyboard shortcuts
document.addEventListener('keydown', function (e) {
    // Enter key to submit form
    if (e.key === 'Enter' && !e.shiftKey) {
        const activeElement = document.activeElement;
        if (activeElement && activeElement.classList.contains('form-input')) {
            const form = activeElement.closest('form');
            if (form) {
                form.dispatchEvent(new Event('submit'));
            }
        }
    }

    // Escape key to clear form
    if (e.key === 'Escape') {
        const inputs = document.querySelectorAll('.form-input');
        inputs.forEach(input => {
            input.value = '';
            input.classList.remove('valid', 'invalid');
            removeErrorMessage(input);
        });
    }
});

// Add form auto-save functionality
function saveFormData() {
    const formData = {
        username: document.getElementById('username').value,
        remember: document.getElementById('remember_me').checked
    };

    if (formData.username) {
        localStorage.setItem('loginFormData', JSON.stringify(formData));
    }
}

function loadFormData() {
    const savedData = localStorage.getItem('loginFormData');
    if (savedData) {
        const formData = JSON.parse(savedData);
        document.getElementById('username').value = formData.username || '';
        document.getElementById('remember_me').checked = formData.remember || false;
    }
}

// Load saved form data on page load
document.addEventListener('DOMContentLoaded', function () {
    loadFormData();

    // Save form data on input change
    const usernameInput = document.getElementById('username');
    const rememberCheckbox = document.getElementById('remember_me');

    if (usernameInput) {
        usernameInput.addEventListener('input', saveFormData);
    }

    if (rememberCheckbox) {
        rememberCheckbox.addEventListener('change', saveFormData);
    }
});

// Add smooth scrolling for better UX
document.documentElement.style.scrollBehavior = 'smooth';

// Add loading states for better UX
function addLoadingStates() {
    const loginBtn = document.getElementById('loginBtn');

    if (loginBtn) {
        loginBtn.addEventListener('click', function () {
            // Add ripple effect
            const ripple = document.createElement('span');
            ripple.className = 'ripple';
            ripple.style.cssText = `
                position: absolute;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.3);
                transform: scale(0);
                animation: ripple 0.6s linear;
                pointer-events: none;
            `;

            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = (event.clientX - rect.left - size / 2) + 'px';
            ripple.style.top = (event.clientY - rect.top - size / 2) + 'px';

            this.appendChild(ripple);

            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    }
}

// Initialize loading states
document.addEventListener('DOMContentLoaded', addLoadingStates);

// Add CSS for ripple effect
const style = document.createElement('style');
style.textContent = `
    @keyframes ripple {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }

    .form-input.valid {
        border-color: #48bb78 !important;
        box-shadow: 0 0 0 3px rgba(72, 187, 120, 0.1) !important;
    }

    .form-input.invalid {
        border-color: #e53e3e !important;
        box-shadow: 0 0 0 3px rgba(229, 62, 62, 0.1) !important;
    }
`;
document.head.appendChild(style);
