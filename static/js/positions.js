document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const positionModal = document.getElementById('positionModal');
    const positionForm = document.getElementById('positionForm');
    const loading = document.getElementById('loading');
    const addPositionBtn = document.getElementById('addPositionBtn');
    const modalTitle = document.getElementById('modalTitle');
    const closeModal = document.getElementById('closeModal');
    const cancelBtn = document.getElementById('cancelBtn');

    // Debug: Check if elements exist
    console.log("Add Position Button:", addPositionBtn);
    console.log("Position Modal:", positionModal);
    console.log("Position Form:", positionForm);

    // Open Add Position Modal
    if (addPositionBtn) {
        addPositionBtn.addEventListener('click', function() {
            console.log("Add Position button clicked");
            openPositionModal();
        });
    } else {
        console.error("Add Position button not found!");
    }

    // Function to open modal for adding new position
    function openPositionModal() {
        if (positionModal) {
            modalTitle.textContent = 'Add New Position';
            document.querySelector('button[type="submit"]').textContent = 'Add Position';

            // Reset form and set default values
            if (positionForm) {
                positionForm.reset();
                positionForm.action = "{% url 'add_position' %}";
                document.getElementById('positionId').value = '';
                document.getElementById('positionStatus').value = 'active';
            }

            positionModal.style.display = 'block';
        } else {
            console.error("Position modal not found!");
        }
    }

    // Function to open modal for editing position
    function openEditModal(positionId, positionName, positionDescription, positionStatus) {
        if (positionModal) {
            modalTitle.textContent = 'Edit Position';
            document.querySelector('button[type="submit"]').textContent = 'Update Position';

            // Fill the form with position data
            document.getElementById('positionId').value = positionId;
            document.getElementById('positionName').value = positionName;
            document.getElementById('positionDescription').value = positionDescription;
            document.getElementById('positionStatus').value = positionStatus;

            // Set form action for update
            positionForm.action = "{% url 'update_position' 0 %}".replace('0', positionId);

            positionModal.style.display = 'block';
        }
    }

    // Close modal functionality
    function closePositionModal() {
        if (positionModal) {
            positionModal.style.display = 'none';
        }
    }

    if (closeModal) {
        closeModal.addEventListener('click', closePositionModal);
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', closePositionModal);
    }

    // Close modal when clicking outside
    if (positionModal) {
        positionModal.addEventListener('click', function(e) {
            if (e.target === positionModal) {
                closePositionModal();
            }
        });
    }

    // Close modal with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && positionModal && positionModal.style.display === 'block') {
            closePositionModal();
        }
    });

    // Add event listeners to edit buttons
    document.querySelectorAll('.edit-position').forEach(btn => {
        btn.addEventListener('click', function() {
            const positionId = this.getAttribute('data-id');
            const positionName = this.getAttribute('data-name');
            const positionDescription = this.getAttribute('data-description');
            const positionStatus = this.getAttribute('data-status');

            openEditModal(positionId, positionName, positionDescription, positionStatus);
        });
    });

    // Form validation
    if (positionForm) {
        positionForm.addEventListener('submit', function(e) {
            const positionName = document.getElementById('positionName').value.trim();
            if (!positionName) {
                e.preventDefault();
                alert('Position name is required!');
                document.getElementById('positionName').focus();
                return false;
            }

            // Show loading indicator if available
            if (loading) {
                loading.style.display = 'flex';
            }

            return true;
        });
    }

    // Animate elements on scroll
    const animateOnScroll = function() {
        const elements = document.querySelectorAll('.fade-in-up');
        elements.forEach(element => {
            const elementPosition = element.getBoundingClientRect().top;
            const screenPosition = window.innerHeight / 1.3;
            if (elementPosition < screenPosition) {
                element.style.opacity = 1;
                element.style.transform = 'translateY(0)';
            }
        });
    };

    // Initial check on load
    animateOnScroll();

    // Check on scroll
    window.addEventListener('scroll', animateOnScroll);

    // Splash screen handling - Now handled by splash.js for consistency
    // Keeping this for backward compatibility but splash.js takes precedence
    const splashScreen = document.getElementById('splashScreen');
    if (splashScreen && !window.splashScreenHandled) {
        // Hide the splash screen after 2 seconds
        setTimeout(function() {
            splashScreen.style.opacity = '0';
            setTimeout(function() {
                splashScreen.style.display = 'none';
            }, 400);
        }, 2000); // Display time: 2 seconds
    }

    // Remove any existing sample data initialization
    console.log("Position management initialized successfully");
});