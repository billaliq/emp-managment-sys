// Shared Splash Screen Handler - Shorter Loading Duration
document.addEventListener('DOMContentLoaded', function() {
    const splashScreen = document.getElementById('splashScreen');

    if (splashScreen) {
        // Mark as handled to prevent conflicts with other scripts
        window.splashScreenHandled = true;

        // Show splash screen immediately
        splashScreen.style.display = 'flex';
        splashScreen.style.opacity = '1';

        // Hide splash screen after 2 seconds
        setTimeout(function() {
            splashScreen.style.opacity = '0';
            setTimeout(function() {
                splashScreen.style.display = 'none';
            }, 400); // Fade out duration (400ms)
        }, 2000); // Display time: 2 seconds
    }
});

