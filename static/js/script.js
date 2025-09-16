document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    })
    
    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'))
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl)
    })
    
    // Initialize maps
    if (typeof L !== 'undefined') {
        initializeMaps();
    }
    
    // Initialize charts
    if (typeof Chart !== 'undefined') {
        initializeCharts();
    }
    
    // Device control buttons
    const controlButtons = document.querySelectorAll('.device-control');
    controlButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const deviceId = this.getAttribute('data-device-id');
            const command = this.getAttribute('data-command');
            
            controlDevice(deviceId, command);
        });
    });
    
    // Real-time data updates
    if (window.location.pathname === '/' || window.location.pathname === '/device') {
        setInterval(updateDeviceStatuses, 30000); // Update every 30 seconds
    }
});

function initializeMaps() {
    const mapElements = document.querySelectorAll('.farm-map');
    
    mapElements.forEach(element => {
        const mapId = element.id;
        const lat = parseFloat(element.getAttribute('data-lat'));
        const lng = parseFloat(element.getAttribute('data-lng'));
        const farmName = element.getAttribute('data-farm-name');
        
        const map = L.map(mapId).setView([lat, lng], 13);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);
        
        L.marker([lat, lng]).addTo(map)
            .bindPopup(farmName)
            .openPopup();
    });
}

function initializeCharts() {
    const chartElements = document.querySelectorAll('.sensor-chart');
    
    chartElements.forEach(element => {
        const ctx = element.getContext('2d');
        const chartType = element.getAttribute('data-chart-type') || 'line';
        const labels = JSON.parse(element.getAttribute('data-labels') || '[]');
        const data = JSON.parse(element.getAttribute('data-values') || '[]');
        const label = element.getAttribute('data-label') || 'Value';
        const borderColor = element.getAttribute('data-border-color') || 'rgb(75, 192, 192)';
        const backgroundColor = element.getAttribute('data-background-color') || 'rgba(75, 192, 192, 0.2)';
        
        new Chart(ctx, {
            type: chartType,
            data: {
                labels: labels,
                datasets: [{
                    label: label,
                    data: data,
                    borderColor: borderColor,
                    backgroundColor: backgroundColor,
                    tension: 0.1,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    });
}

function controlDevice(deviceId, command) {
    fetch(`/device/${deviceId}/control/${command}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                // Update button appearance
                const button = document.querySelector(`.device-control[data-device-id="${deviceId}"][data-command="${command}"]`);
                const otherButton = document.querySelector(`.device-control[data-device-id="${deviceId}"][data-command="${command === 'on' ? 'off' : 'on'}"]`);
                
                if (command === 'on') {
                    button.classList.add('active');
                    otherButton.classList.remove('active');
                } else {
                    button.classList.add('active');
                    otherButton.classList.remove('active');
                }
                
                // Update status badge
                const statusBadge = document.querySelector(`#device-${deviceId}-status`);
                if (statusBadge) {
                    statusBadge.textContent = command === 'on' ? 'ON' : 'OFF';
                    statusBadge.className = `device-status status-${command}`;
                }
            } else {
                showAlert(data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Terjadi kesalahan saat mengontrol perangkat', 'danger');
        });
}

function updateDeviceStatuses() {
    // This would typically fetch the latest status from the server
    // For now, we'll just simulate an update
    console.log('Updating device statuses...');
}

function showAlert(message, type) {
    const alertContainer = document.getElementById('alert-container');
    if (!alertContainer) {
        // Create alert container if it doesn't exist
        const container = document.createElement('div');
        container.id = 'alert-container';
        container.className = 'position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1050';
        document.body.appendChild(container);
    }
    
    const alertId = 'alert-' + Date.now();
    const alertHtml = `
        <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    
    document.getElementById('alert-container').insertAdjacentHTML('beforeend', alertHtml);
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        const alert = document.getElementById(alertId);
        if (alert) {
            bootstrap.Alert.getOrCreateInstance(alert).close();
        }
    }, 5000);
}

// Form validation
(function () {
    'use strict'
    
    // Fetch all the forms we want to apply custom Bootstrap validation styles to
    var forms = document.querySelectorAll('.needs-validation')
    
    // Loop over them and prevent submission
    Array.prototype.slice.call(forms)
        .forEach(function (form) {
            form.addEventListener('submit', function (event) {
                if (!form.checkValidity()) {
                    event.preventDefault()
                    event.stopPropagation()
                }
                
                form.classList.add('was-validated')
            }, false)
        })
})()