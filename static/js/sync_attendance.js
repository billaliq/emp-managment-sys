
document.addEventListener('DOMContentLoaded', function() {
    const syncBtn = document.getElementById('syncAttendanceBtn');
    if (syncBtn) {
        syncBtn.addEventListener('click', function() {
            if (this.disabled) return;
            
            this.disabled = true;
            const originalText = this.innerHTML;
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Syncing...';
            
            // Show notification
            const notification = document.createElement('div');
            notification.className = 'alert alert-info';
            notification.style.position = 'fixed';
            notification.style.top = '20px';
            notification.style.right = '20px';
            notification.style.zIndex = '9999';
            notification.innerHTML = 'Connecting to devices to fetch attendance...';
            document.body.appendChild(notification);
            
            fetch('/import-attendance/')
                .then(response => response.json())
                .then(data => {
                    notification.remove();
                    
                    if (data.status === 'success' || data.status === 'warning') {
                        // Success alert
                        const successAlert = document.createElement('div');
                        successAlert.className = `alert alert-${data.status === 'success' ? 'success' : 'warning'}`;
                        successAlert.style.position = 'fixed';
                        successAlert.style.top = '20px';
                        successAlert.style.right = '20px';
                        successAlert.style.zIndex = '9999';
                        successAlert.innerHTML = data.message;
                        document.body.appendChild(successAlert);
                        
                        // Reload after 2 seconds
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    } else {
                        // Error alert
                        alert('Error: ' + data.message);
                        this.disabled = false;
                        this.innerHTML = originalText;
                    }
                })
                .catch(error => {
                    notification.remove();
                    console.error('Error:', error);
                    alert('An error occurred while syncing.');
                    this.disabled = false;
                    this.innerHTML = originalText;
                });
        });
    }
});
