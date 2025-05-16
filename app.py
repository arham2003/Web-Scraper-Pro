from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, send_from_directory
import os
import json
import threading
import uuid
import time
import io
import zipfile
from datetime import datetime
from selenium_scraper.script import setup_driver, scrape_websites, scrape_google_images

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'output'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Create necessary directories
os.makedirs('output/images', exist_ok=True)
os.makedirs('output/debug', exist_ok=True)
os.makedirs('output/screenshots', exist_ok=True)

# Store scraping tasks
tasks = {}
# Store logs for each task
task_logs = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/loading/<task_id>')
def loading(task_id):
    task_type = tasks.get(task_id, {}).get('type', 'unknown')
    return render_template('loading.html', task_id=task_id, task_type=task_type)

@app.route('/results/<task_id>')
def results(task_id):
    if task_id not in tasks:
        return redirect(url_for('index'))
    
    task = tasks[task_id]
    return render_template('results.html', task=task, task_id=task_id)

def add_log(task_id, message):
    """Add a log message for a task"""
    if task_id not in task_logs:
        task_logs[task_id] = []
    task_logs[task_id].append({
        'time': datetime.now().strftime('%H:%M:%S'),
        'message': message
    })

@app.route('/task_logs/<task_id>')
def get_task_logs(task_id):
    if task_id not in task_logs:
        return jsonify([])
    return jsonify(task_logs[task_id])

@app.route('/scrape_website', methods=['POST'])
def scrape_website():
    urls = request.form.get('urls', '').split()
    if not urls:
        return jsonify({'error': 'No URLs provided'}), 400
    
    # Ensure all URLs have proper HTTP prefix
    processed_urls = []
    for url in urls:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        processed_urls.append(url)
    
    max_scrolls = int(request.form.get('max_scrolls', 5))
    take_screenshots = request.form.get('take_screenshots') == 'on'
    
    # Generate unique task ID and output file
    task_id = str(uuid.uuid4())
    output_file = f"output/scraper_results_{task_id}.json"
    
    # Initialize task data
    tasks[task_id] = {
        'type': 'website',
        'status': 'running',
        'progress': 0,
        'output_file': output_file,
        'urls': processed_urls,
        'results': None,
        'screenshots': [],
        'take_screenshots': take_screenshots,
        'timestamp': datetime.now().isoformat()
    }
    
    # Initialize logs
    add_log(task_id, f"Starting website scraping for URLs: {', '.join(processed_urls)}")
    
    # Start scraping in a background thread
    def run_scraper():
        driver = None
        try:
            add_log(task_id, "Setting up browser...")
            driver = setup_driver(headless=False)
            
            add_log(task_id, "Beginning scraping process...")
            results, screenshots = scrape_websites(driver, processed_urls, output_file, max_scrolls, take_screenshots)
            
            add_log(task_id, "Scraping completed successfully!")
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['results'] = results
            
            # Ensure the file path is absolute and correct
            if os.path.exists(output_file):
                tasks[task_id]['output_file'] = os.path.abspath(output_file)
                add_log(task_id, f"Results saved to: {os.path.abspath(output_file)}")
            else:
                add_log(task_id, f"Warning: Output file not found at {output_file}")
                # Try to find the file elsewhere
                possible_path = os.path.join(os.getcwd(), output_file)
                if os.path.exists(possible_path):
                    tasks[task_id]['output_file'] = possible_path
                    add_log(task_id, f"Results found at alternate path: {possible_path}")
            
            # Store screenshot information
            if take_screenshots and screenshots:
                tasks[task_id]['screenshots'] = screenshots
                add_log(task_id, f"Saved {len(screenshots)} screenshots.")
                
        except Exception as e:
            add_log(task_id, f"Error during scraping: {str(e)}")
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)
        finally:
            # Always quit the driver in the finally block to ensure it closes
            if driver:
                try:
                    driver.quit()
                    add_log(task_id, "Browser closed successfully.")
                except Exception as e:
                    add_log(task_id, f"Error closing browser: {str(e)}")
    
    thread = threading.Thread(target=run_scraper)
    thread.daemon = True
    thread.start()
    
    return jsonify({'task_id': task_id})

@app.route('/scrape_images', methods=['POST'])
def scrape_images():
    query = request.form.get('query', '')
    if not query:
        return jsonify({'error': 'No search query provided'}), 400
    
    num_images = int(request.form.get('num_images', 20))
    
    # Generate unique task ID and output folder
    task_id = str(uuid.uuid4())
    output_folder = f"output/images/{task_id}"
    os.makedirs(output_folder, exist_ok=True)
    
    # Initialize task data
    tasks[task_id] = {
        'type': 'images',
        'status': 'running',
        'progress': 0,
        'query': query,
        'output_folder': output_folder,
        'image_count': 0,
        'images': [],
        'timestamp': datetime.now().isoformat()
    }
    
    # Initialize logs
    add_log(task_id, f"Starting image search for query: {query}")
    
    # Start scraping in a background thread
    def run_image_scraper():
        driver = None
        try:
            add_log(task_id, "Setting up browser...")
            driver = setup_driver(headless=False)
            
            add_log(task_id, f"Searching Google Images for '{query}'...")
            # Pass the number of images to search for
            successful_downloads, folder_path = scrape_google_images(driver, query, num_images, output_folder)
            
            add_log(task_id, f"Downloaded {successful_downloads} images successfully!")
            
            # Get image paths
            image_files = []
            if folder_path and os.path.exists(folder_path):
                for file in os.listdir(folder_path):
                    if file.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                        image_files.append(os.path.join(folder_path, file))
            
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['image_count'] = successful_downloads
            tasks[task_id]['images'] = image_files
        except Exception as e:
            add_log(task_id, f"Error during image scraping: {str(e)}")
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)
        finally:
            # Always quit the driver in the finally block to ensure it closes
            if driver:
                try:
                    driver.quit()
                    add_log(task_id, "Browser closed successfully.")
                except Exception as e:
                    add_log(task_id, f"Error closing browser: {str(e)}")
    
    thread = threading.Thread(target=run_image_scraper)
    thread.daemon = True
    thread.start()
    
    return jsonify({'task_id': task_id})

@app.route('/task_status/<task_id>')
def task_status(task_id):
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify(tasks[task_id])

@app.route('/download/<task_id>')
def download_results(task_id):
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = tasks[task_id]
    
    if task['type'] == 'website' and task['status'] == 'completed':
        # Get the output file path from the task
        output_file = task['output_file']
        
        # Check if the file exists
        if os.path.exists(output_file):
            return send_file(output_file, as_attachment=True)
        else:
            # Try different path variations
            alt_paths = [
                os.path.join(os.getcwd(), output_file),
                os.path.join('output', f"scraper_results_{task_id}.json")
            ]
            
            # Print debug info
            print(f"Original file path not found: {output_file}")
            print(f"Looking for alternative paths: {alt_paths}")
            
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    print(f"Found file at: {alt_path}")
                    return send_file(alt_path, as_attachment=True)
            
            # If we get here, file was not found
            return jsonify({'error': f'File not found: {output_file}'}), 404
    else:
        return jsonify({'error': 'No downloadable content available for this task'}), 400

@app.route('/images/<task_id>')
def get_task_images(task_id):
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = tasks[task_id]
    
    if task['type'] == 'images' and task['status'] == 'completed':
        return jsonify({
            'image_count': task['image_count'],
            'images': [os.path.basename(img) for img in task['images']]
        })
    else:
        return jsonify({'error': 'No images available for this task'}), 400

@app.route('/image/<task_id>/<filename>')
def get_image(task_id, filename):
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = tasks[task_id]
    
    if task['type'] == 'images' and task['status'] == 'completed':
        for img_path in task['images']:
            if os.path.basename(img_path) == filename:
                return send_file(img_path)
    
    return jsonify({'error': 'Image not found'}), 404

@app.route('/download_images_zip/<task_id>')
def download_images_zip(task_id):
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = tasks[task_id]
    
    if task['type'] == 'images' and task['status'] == 'completed':
        memory_file = io.BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w') as zf:
            for img_path in task['images']:
                filename = os.path.basename(img_path)
                zf.write(img_path, filename)
        
        memory_file.seek(0)
        
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"images_{task['query'].replace(' ', '_')}_{task_id[:8]}.zip"
        )
    
    return jsonify({'error': 'No images available for this task'}), 400

@app.route('/screenshot/<task_id>/<filename>')
def get_screenshot(task_id, filename):
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    # Look for the screenshot in the task data
    task = tasks[task_id]
    if task['type'] == 'website' and task.get('screenshots'):
        for screenshot in task['screenshots']:
            if screenshot['filename'] == filename:
                screenshot_path = os.path.join('output', 'screenshots', filename)
                
                if os.path.exists(screenshot_path):
                    return send_file(screenshot_path)
    
    return jsonify({'error': 'Screenshot not found'}), 404

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/list_files')
def list_files():
    """Debug route to list all available files in the output directory"""
    output_dir = 'output'
    
    if not os.path.exists(output_dir):
        return jsonify({'error': 'Output directory does not exist'}), 404
    
    # List all files in the output directory
    files = []
    for root, dirs, filenames in os.walk(output_dir):
        for filename in filenames:
            if filename.endswith('.json'):
                file_path = os.path.join(root, filename)
                file_size = os.path.getsize(file_path)
                files.append({
                    'path': file_path,
                    'size': file_size,
                    'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                })
    
    # List file paths in each task
    task_files = {}
    for task_id, task in tasks.items():
        if task.get('type') == 'website' and task.get('output_file'):
            output_file = task['output_file']
            task_files[task_id] = {
                'path': output_file,
                'exists': os.path.exists(output_file),
                'absolute_path': os.path.abspath(output_file)
            }
    
    return jsonify({
        'current_directory': os.getcwd(),
        'available_files': files,
        'task_files': task_files
    })

@app.route('/download_file/<filename>')
def download_file(filename):
    """Direct download route for any file in the output directory"""
    # Check if the file exists directly in the output directory
    file_path = os.path.join('output', filename)
    
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    
    # If not found, check if it's a task ID and try to find the file
    for task_id, task in tasks.items():
        if task_id in filename and task.get('output_file'):
            if os.path.exists(task['output_file']):
                return send_file(task['output_file'], as_attachment=True)
    
    return jsonify({'error': 'File not found'}), 404

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 