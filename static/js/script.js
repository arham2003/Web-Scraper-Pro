/**
 * Web Scraper Pro - Advanced JavaScript Functions
 */

// Store all tasks and their data in localStorage
const taskStorage = {
    saveTask(taskId, taskData) {
        const tasks = this.getAllTasks();
        tasks[taskId] = taskData;
        localStorage.setItem('webScraperTasks', JSON.stringify(tasks));
    },

    getTask(taskId) {
        const tasks = this.getAllTasks();
        return tasks[taskId] || null;
    },

    getAllTasks() {
        const tasksJson = localStorage.getItem('webScraperTasks');
        return tasksJson ? JSON.parse(tasksJson) : {};
    },

    removeTask(taskId) {
        const tasks = this.getAllTasks();
        if (tasks[taskId]) {
            delete tasks[taskId];
            localStorage.setItem('webScraperTasks', JSON.stringify(tasks));
            return true;
        }
        return false;
    }
};

// Display notification to the user
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type} slide-up`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : 
                           type === 'error' ? 'fa-exclamation-circle' : 
                           'fa-info-circle'}"></i>
            <span>${message}</span>
        </div>
        <button class="notification-close">&times;</button>
    `;
    
    // Add to document
    document.body.appendChild(notification);
    
    // Add close button functionality
    const closeBtn = notification.querySelector('.notification-close');
    closeBtn.addEventListener('click', () => {
        notification.classList.add('slide-out');
        setTimeout(() => {
            notification.remove();
        }, 300);
    });
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (document.body.contains(notification)) {
            notification.classList.add('slide-out');
            setTimeout(() => {
                notification.remove();
            }, 300);
        }
    }, 5000);
}

// Add event listener for the selenium window detection
function watchSeleniumWindow(taskId, taskType) {
    // Poll window status every 2 seconds
    const checkInterval = setInterval(() => {
        fetch(`/task_status/${taskId}`)
            .then(response => response.json())
            .then(data => {
                // If the task is completed or failed, we stop checking
                if (data.status === 'completed' || data.status === 'failed') {
                    clearInterval(checkInterval);
                    
                    // Show notification
                    if (data.status === 'completed') {
                        const message = taskType === 'website' 
                            ? `Successfully scraped ${data.urls.length} website(s)`
                            : `Successfully downloaded ${data.image_count} image(s)`;
                        showNotification(message, 'success');
                    } else {
                        showNotification(`Task failed: ${data.error || 'Unknown error'}`, 'error');
                    }
                    
                    // Store task data in localStorage
                    data.timestamp = new Date().toISOString();
                    taskStorage.saveTask(taskId, data);
                    
                    // If we're on the index page and the previousTasksContainer exists,
                    // reload the previous tasks to show the new one
                    if (document.getElementById('previousTasksContainer')) {
                        loadPreviousTasks();
                    }
                }
            })
            .catch(error => console.error('Error checking task status:', error));
    }, 2000);
}

// Function to create a zip file from images for download
function createImageZip(taskId, imageUrls) {
    return new Promise((resolve, reject) => {
        if (!imageUrls || imageUrls.length === 0) {
            reject('No images to download');
            return;
        }
        
        // Use JSZip library if available
        if (typeof JSZip !== 'undefined') {
            const zip = new JSZip();
            const folder = zip.folder(`images_${taskId}`);
            
            let downloadCount = 0;
            const totalImages = imageUrls.length;
            
            imageUrls.forEach((url, index) => {
                const filename = url.split('/').pop();
                
                // Fetch the image
                fetch(url)
                    .then(response => response.blob())
                    .then(blob => {
                        folder.file(filename, blob);
                        downloadCount++;
                        
                        if (downloadCount === totalImages) {
                            // Generate the zip file
                            zip.generateAsync({type: 'blob'})
                                .then(content => {
                                    resolve(content);
                                });
                        }
                    })
                    .catch(error => {
                        console.error('Error downloading image:', error);
                        downloadCount++;
                        
                        if (downloadCount === totalImages) {
                            // Generate the zip file even if some images failed
                            zip.generateAsync({type: 'blob'})
                                .then(content => {
                                    resolve(content);
                                });
                        }
                    });
            });
        } else {
            // Fallback if JSZip is not available
            reject('JSZip library not available');
        }
    });
}

// Load previous tasks if available
function loadPreviousTasks() {
    const tasks = taskStorage.getAllTasks();
    
    if (Object.keys(tasks).length > 0) {
        // Create previous tasks section if it doesn't exist
        let prevTasksSection = document.getElementById('previousTasks');
        
        if (!prevTasksSection) {
            // Use the dedicated container instead of the main container
            const container = document.getElementById('previousTasksContainer');
            
            prevTasksSection = document.createElement('div');
            prevTasksSection.id = 'previousTasks';
            prevTasksSection.className = 'row mt-4';
            prevTasksSection.innerHTML = `
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <i class="fas fa-history me-2"></i> Previous Tasks
                                </div>
                                <button id="clearHistory" class="btn btn-sm btn-outline-light">
                                    <i class="fas fa-trash-alt me-1"></i> Clear History
                                </button>
                            </div>
                        </div>
                        <div class="card-body">
                            <div id="tasksList" class="list-group"></div>
                        </div>
                    </div>
                </div>
            `;
            
            // Append to the dedicated container
            container.appendChild(prevTasksSection);
            
            // Add clear history button functionality
            document.getElementById('clearHistory').addEventListener('click', () => {
                if (confirm('Are you sure you want to clear your task history?')) {
                    localStorage.removeItem('webScraperTasks');
                    prevTasksSection.remove();
                    showNotification('Task history cleared', 'info');
                }
            });
        }
        
        // Add tasks to the list
        const tasksList = document.getElementById('tasksList');
        tasksList.innerHTML = '';
        
        Object.entries(tasks).forEach(([taskId, task]) => {
            const taskDate = task.timestamp ? new Date(task.timestamp).toLocaleString() : 'Unknown date';
            const taskItem = document.createElement('div');
            taskItem.className = 'list-group-item list-group-item-action';
            
            let taskContent = '';
            if (task.type === 'website') {
                taskContent = `
                    <div class="d-flex w-100 justify-content-between">
                        <h5 class="mb-1">Website Scraping</h5>
                        <small>${taskDate}</small>
                    </div>
                    <p class="mb-1">URLs: ${task.urls.join(', ')}</p>
                    <div class="d-flex justify-content-end">
                        <button class="btn btn-sm btn-primary reload-task" data-task-id="${taskId}">
                            <i class="fas fa-sync-alt me-1"></i> Reload
                        </button>
                        <button class="btn btn-sm btn-primary ms-2" onclick="window.location.href='/download/${taskId}'">
                            <i class="fas fa-download me-1"></i> Download
                        </button>
                    </div>
                `;
            } else if (task.type === 'images') {
                taskContent = `
                    <div class="d-flex w-100 justify-content-between">
                        <h5 class="mb-1">Image Search: ${task.query}</h5>
                        <small>${taskDate}</small>
                    </div>
                    <p class="mb-1">Downloaded: ${task.image_count} images</p>
                    <div class="d-flex justify-content-end">
                        <button class="btn btn-sm btn-primary reload-task" data-task-id="${taskId}">
                            <i class="fas fa-sync-alt me-1"></i> Reload
                        </button>
                        <button class="btn btn-sm btn-primary ms-2 view-images" data-task-id="${taskId}">
                            <i class="fas fa-images me-1"></i> View Images
                        </button>
                    </div>
                `;
            }
            
            taskItem.innerHTML = taskContent;
            tasksList.appendChild(taskItem);
        });
        
        // Add reload task functionality
        document.querySelectorAll('.reload-task').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const taskId = e.currentTarget.getAttribute('data-task-id');
                const task = taskStorage.getTask(taskId);
                
                if (task) {
                    if (task.type === 'website') {
                        document.getElementById('websiteUrls').value = task.urls.join(' ');
                        document.getElementById('websiteForm').dispatchEvent(new Event('submit'));
                    } else if (task.type === 'images') {
                        document.getElementById('imageQuery').value = task.query;
                        document.getElementById('imagesForm').dispatchEvent(new Event('submit'));
                    }
                }
            });
        });
        
        // Add view images functionality
        document.querySelectorAll('.view-images').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const taskId = e.currentTarget.getAttribute('data-task-id');
                loadImageGalleryFromTask(taskId);
            });
        });
    }
}

// Load image gallery from a previous task
function loadImageGalleryFromTask(taskId) {
    const task = taskStorage.getTask(taskId);
    
    if (task && task.type === 'images') {
        // Update the form with the task query
        document.getElementById('imageQuery').value = task.query;
        
        // Show the images results section
        const imagesResults = document.getElementById('imagesResults');
        imagesResults.style.display = 'block';
        
        // Update results summary
        const imagesResultsSummary = document.getElementById('imagesResultsSummary');
        imagesResultsSummary.textContent = `Successfully downloaded ${task.image_count} image${task.image_count !== 1 ? 's' : ''}`;
        
        // Load images into gallery
        fetch(`/images/${taskId}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error('Error:', data.error);
                    return;
                }
                
                // Clear existing images
                const imageGallery = document.getElementById('imageGallery');
                imageGallery.innerHTML = '';
                
                // Add images to gallery
                data.images.forEach(filename => {
                    const img = document.createElement('img');
                    img.src = `/image/${taskId}/${filename}`;
                    img.alt = filename;
                    img.className = 'image-thumbnail';
                    img.onclick = function() {
                        window.open(this.src, '_blank');
                    };
                    imageGallery.appendChild(img);
                });
                
                // Scroll to the images section
                imagesResults.scrollIntoView({ behavior: 'smooth' });
            })
            .catch(error => {
                console.error('Error:', error);
            });
    }
}

// Initialize the app when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check for dark mode preference
    const darkModePreference = window.matchMedia('(prefers-color-scheme: dark)');
    if (darkModePreference.matches) {
        document.body.classList.add('dark-mode');
    }
    
    // Add timestamp to tasks and save to localStorage - utility function
    const addTaskTimestamp = (taskId) => {
        fetch(`/task_status/${taskId}`)
            .then(response => response.json())
            .then(data => {
                if (data) {
                    data.timestamp = new Date().toISOString();
                    taskStorage.saveTask(taskId, data);
                }
            })
            .catch(error => console.error('Error adding timestamp:', error));
    };

    // Load previous tasks when the page loads
    setTimeout(() => {
        // Add some delay to ensure task container is ready
        loadPreviousTasks();
    }, 100);
    
    // Event handlers for forms are now in index.html
    // This avoids duplicate event handlers
    
    // Add resize event listener for responsive design
    window.addEventListener('resize', function() {
        const width = window.innerWidth;
        const cards = document.querySelectorAll('.card');
        
        if (width < 768) {
            cards.forEach(card => {
                card.classList.add('mobile-view');
            });
        } else {
            cards.forEach(card => {
                card.classList.remove('mobile-view');
            });
        }
    });
    
    // Trigger resize event once to set initial state
    window.dispatchEvent(new Event('resize'));
}); 