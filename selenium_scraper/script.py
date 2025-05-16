# 22k-4080, 22k-4004
#BAI-6B

import os
import sys
import json
import time
import logging
import urllib.parse
import urllib.request
import re
from datetime import datetime
from urllib.parse import urlparse, urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# loggin setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# ===== Selenium Scraper Functions =====

def setup_driver(headless=False):
    
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)
    logger.info("Selenium WebDriver initialized successfully")
    return driver

def get_page(driver, url, timeout=30):
    """
    Load a page with Selenium and handle dynamic content
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    driver.get(url)
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    return True

def handle_infinite_scroll(driver, max_scrolls=5, scroll_pause_time=1):
    """
    Handle infinite scrolling on pages
    """
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    for i in range(max_scrolls):
        logger.info(f"Scroll attempt {i+1}/{max_scrolls}")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            logger.info("Reached bottom of page")
            break
        last_height = new_height

def click_load_more_buttons(driver, scroll_pause_time=1.5):
    """
    Find and click 'Load More' buttons
    """
    button_patterns = [
        "//button[contains(text(), 'Load More')]",
        "//button[contains(text(), 'Show More')]",
        "//a[contains(text(), 'Load More')]",
        "//a[contains(text(), 'Show More')]",
        "//div[contains(@class, 'load-more')]",
        "//div[contains(@class, 'show-more')]",
        "//span[contains(text(), 'Load More')]",
    ]
    
    for pattern in button_patterns:
        try:
            buttons = driver.find_elements(By.XPATH, pattern)
            if buttons:
                logger.info(f"Found {len(buttons)} load more button(s)")
                for button in buttons:
                    if button.is_displayed():
                        button.click()
                        time.sleep(scroll_pause_time)
        except:
            continue

def parse_page(driver, url):
    """
    Parse the page after dynamic content is loaded
    """
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    
 
    data = {
        'url': url,
        'title': soup.title.string.strip() if soup.title else '',
        'links': [],
        'images': [],
        'timestamp': datetime.now().isoformat()
    }
    
    main_content = None
    for tag_name in ['main', 'article']:
        main_tag = soup.find(tag_name)
        if main_tag:
            main_content = main_tag
            break
            
    if not main_content:
        for content_id in ['content', 'main', 'main-content', 'article', 'post']:
            content_div = soup.find('div', id=content_id)
            if content_div:
                main_content = content_div
                break
                
    if not main_content:
        main_content = soup.body
        
    # Clean content
    if main_content:
        for script in main_content.find_all(['script', 'style']):
            script.extract()
        
        content_text = main_content.get_text(separator=' ', strip=True)
        data['content'] = content_text
    else:
        data['content'] = ''
        
    # Extract links
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if href and not href.startswith(('javascript:', '#')):
            absolute_url = urljoin(url, href)
            data['links'].append(absolute_url)
            
    # Extract images
    for img_tag in soup.find_all('img', src=True):
        src = img_tag['src']
        if src:
            absolute_url = urljoin(url, src)
            data['images'].append(absolute_url)
            
    return data

def save_data(data, output_file):
    """
    Save the extracted data to a file
    """
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Save as JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
            
    logger.info(f"Data saved to {output_file}")

def take_screenshot(driver, url, output_dir="output/screenshots"):
    """
    Take a screenshot of the loaded page
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    domain = urlparse(url).netloc
    filename = f"{domain}_{int(time.time())}.png"
    filepath = os.path.join(output_dir, filename)
    
    driver.save_screenshot(filepath)
    logger.info(f"Screenshot saved to {filepath}")
    return filepath

# ===== Google Image Search Functions =====

def google_image_search(driver, query, num_images=20, scroll_pauses=4):
    """
    Search for images on Google and extract their URLs 
    """
    # Clean the search query
    clean_query = query.strip('"\'')
    
    # Encode the search query
    search_url = f"https://www.google.com/search?q={urllib.parse.quote(clean_query)}&tbm=isch"
    logger.info(f"Searching Google Images for: {clean_query}")
    
    # Load the search page
    get_page(driver, search_url)
    
    image_urls = []
    processed_images = 0
    
    for scroll_num in range(scroll_pauses):
        logger.info(f"Processing scroll {scroll_num+1}/{scroll_pauses}")
        
        # Get all image elements in the current view
        img_elements = driver.find_elements(By.CSS_SELECTOR, "img.rg_i, img.Q4LuWd, img")
        logger.info(f"Found {len(img_elements)} image elements in scroll {scroll_num+1}")
        
        # Process each image in this scroll
        for idx, img in enumerate(img_elements):
            if processed_images >= num_images:
                return image_urls
            
            try:
                # Skip tiny images and Google UI elements
                img_src = img.get_attribute('src')
                if not img_src or 'gstatic.com' in img_src or 'google.com/logos' in img_src:
                    continue
                    
                # Check if image is in viewport
                if not is_element_in_viewport(driver, img):
                    continue
                    
                logger.info(f"Clicking image {idx+1} in scroll {scroll_num+1}")
                
                # Click the image to open full size
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img)
                time.sleep(0.5)
                
                # Try to click the image
                img.click()
                time.sleep(1.5)
                
                # Try to find the full-size image URL
                full_image_url = None
                
                # Try different selectors for the full-size image
                for selector in [
                    "img.r48jcc", "img.n3VNCb", "img.iPVvYb",
                    "img[jsname='kn3ccd']", "img[data-noaft='1']"
                ]:
                    try:
                        full_img = WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        url = full_img.get_attribute('src')
                        if url and url.startswith('http') and 'http' in url:
                            full_image_url = url
                            break
                    except:
                        continue
                
                # If we found a valid URL, add it to our list
                if full_image_url and full_image_url.startswith('http') and full_image_url not in image_urls:
                    logger.info(f"Found image URL: {full_image_url[:50]}...")
                    image_urls.append(full_image_url)
                    processed_images += 1
                
                # Go back to search results (press ESC)
                webdriver.ActionChains(driver).send_keys('\ue00c').perform()
                time.sleep(0.5)
                
            except:
                # Reset state by pressing Escape
                try:
                    webdriver.ActionChains(driver).send_keys('\ue00c').perform()
                except:
                    pass
                continue
        
        # After processing all images in current view, scroll down to load more
        if processed_images < num_images and scroll_num < scroll_pauses - 1:
            logger.info(f"Scrolling down for more images ({processed_images}/{num_images} collected so far)")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # Try to dismiss any popups
            try:
                dismiss_buttons = driver.find_elements(By.XPATH, 
                    "//button[contains(text(), 'No thanks') or contains(text(), 'Dismiss') or contains(text(), 'I agree')]")
                for button in dismiss_buttons:
                    if button.is_displayed():
                        button.click()
                        time.sleep(0.5)
            except:
                pass
    
    logger.info(f"Successfully extracted {len(image_urls)} image URLs")
    return image_urls

def is_element_in_viewport(driver, element):
    """Check if an element is in the current viewport"""
    try:
        return driver.execute_script("""
            var elem = arguments[0];
            var rect = elem.getBoundingClientRect();
            return (
                rect.top >= 0 &&
                rect.left >= 0 &&
                rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                rect.right <= (window.innerWidth || document.documentElement.clientWidth)
            );
        """, element)
    except:
        return False

def download_images(image_urls, output_folder, query):
    """
    Download images from URLs to a local folder
    """
    # Create a sanitized folder name based on the query
    safe_query = re.sub(r'[^\w\s-]', '', query).strip().replace(' ', '_')
    folder_path = os.path.join(output_folder, safe_query)
    
    # Create the folder if it doesn't exist
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        
    successful_downloads = 0
    logger.info(f"Downloading {len(image_urls)} images to {folder_path}")
    
    # Set headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for i, url in enumerate(image_urls):
        try:
            # Create a filename for the image
            file_extension = url.split('.')[-1]
            if len(file_extension) > 4 or '/' in file_extension:
                file_extension = 'jpg'
            
            filename = f"{safe_query}_{i+1}.{file_extension}"
            filepath = os.path.join(folder_path, filename)
            
            # Download the image
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response, open(filepath, 'wb') as out_file:
                out_file.write(response.read())
                
            logger.info(f"Downloaded image {i+1}/{len(image_urls)}: {filename}")
            successful_downloads += 1
            
            time.sleep(0.5)
        except:
            logger.error(f"Failed to download image {i+1}")
    
    logger.info(f"Successfully downloaded {successful_downloads} images to {folder_path}")
    return successful_downloads, folder_path


def display_menu():

    print("\n" + "="*50)
    print("             WEB SCRAPER PRO")
    print("="*50)
    print("1. Scrape website content")
    print("2. Scrape Google images")
    print("3. Exit")
    print("="*50)
    choice = input("Enter your choice (1-3): ")
    return choice

def scrape_websites(driver, urls, output_file, max_scrolls=5, take_screenshots=False):
    """
    Scrape content from a list of websites
    """
    results = []
    screenshots = []
    
    for url in urls:
        logger.info(f"Processing URL: {url}")
        
        get_page(driver, url)
        
        # Handle dynamic content
        logger.info("Handling infinite scroll...")
        handle_infinite_scroll(driver, max_scrolls=max_scrolls)
        
        logger.info("Looking for 'load more' buttons...")
        click_load_more_buttons(driver)
        
        # Take a screenshot if requested
        if take_screenshots:
            screenshot_path = take_screenshot(driver, url)
            if screenshot_path:
                # Get just the filename from the path
                screenshot_filename = os.path.basename(screenshot_path)
                # Store the URL and screenshot filename
                screenshots.append({
                    'url': url,
                    'filename': screenshot_filename
                })
                logger.info(f"Screenshot saved for {url}: {screenshot_filename}")
            
        # Parse the page
        logger.info("Parsing page content...")
        data = parse_page(driver, url)
        
        results.append(data)
        logger.info(f"Completed processing: {url}")
    
    # Save all results
    save_data(results, output_file)
    return results, screenshots

def scrape_google_images(driver, query, num_images=20, output_folder="output/images"):
    """
    Scrape images from Google search
    """
    # Search for images
    image_urls = google_image_search(driver, query, num_images=num_images)
    
    # Download the images
    if image_urls:
        successful_downloads, folder_path = download_images(image_urls, output_folder, query)
        return successful_downloads, folder_path
    else:
        logger.error("No image URLs found")
        return 0, None

def main():

    driver = setup_driver(headless=False)
    
    try:
        while True:
            choice = display_menu()
            
            if choice == '1':
                
                url = input("\nEnter the URL to scrape (or multiple URLs separated by space): ")
                urls = url.split()
                
                max_scrolls = int(input("Enter maximum scroll attempts (default 5): ") or 5)
                take_screenshots = input("Take screenshots? (y/n, default n): ").lower() == 'y'
                
                output_file = input("Enter output file path (default: output/scraper_results.json): ")
                if not output_file:
                    output_file = "output/scraper_results.json"
                
                print("\nStarting website scraping...")
                results, screenshots = scrape_websites(driver, urls, output_file, max_scrolls=max_scrolls, take_screenshots=take_screenshots)
                print(f"Website scraping completed. Results saved to {output_file}")
                
                # Display screenshots
                if screenshots:
                    print("\nScreenshots saved for the following URLs:")
                    for screenshot in screenshots:
                        print(f"{screenshot['url']}: {screenshot['filename']}")
            
            elif choice == '2':
                
                query = input("\nEnter the search query for Google Images: ")
                num_images = int(input("Enter number of images to download (default 20): ") or 20)
                output_folder = input("Enter output folder path (default: output/images): ")
                if not output_folder:
                    output_folder = "output/images"
                
                print(f"\nSearching Google Images for '{query}'...")
                successful_downloads, folder_path = scrape_google_images(driver, query, num_images, output_folder)
                
                if successful_downloads > 0:
                    print(f"Image scraping completed. Downloaded {successful_downloads} images to {folder_path}")
                else:
                    print("Image scraping failed. Check the log for details.")
            
            elif choice == '3':
                # Exit
                print("\nExiting Web Scraper Pro. Goodbye!")
                break
            
            else:
                print("\nInvalid choice. Please try again.")
    finally:
        # Clean up
        driver.quit()
        logger.info("WebDriver closed")

if __name__ == "__main__":
    main()