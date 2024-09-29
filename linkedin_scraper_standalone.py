import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

class LinkedinToolException(Exception):
    def __init__(self, message):
        super().__init__(message)

def parse_html_content(page_source: str):
    linkedin_soup = BeautifulSoup(page_source.encode("utf-8"), "lxml")
    containers = linkedin_soup.find_all("div", {"class": "feed-shared-update-v2"})
    containers = [container for container in containers if 'activity' in container.get('data-urn', '')]
    return containers

def get_post_content(container, selector, attributes):
    try:
        element = container.find(selector, attributes)
        if element:
            return element.text.strip()
    except Exception as e:
        print(f"Error getting post content: {e}")
    return ""

def get_linkedin_posts(page_source: str):
    containers = parse_html_content(page_source)
    posts = []
    for container in containers:
        post_content = get_post_content(container, "div", {"class": "update-components-text"})
        posts.append(post_content)
    return posts

def scrape_linkedin_posts():
    linkedin_username = os.environ.get("LINKEDIN_EMAIL")
    linkedin_password = os.environ.get("LINKEDIN_PASSWORD")
    linkedin_profile_name = os.environ.get("LINKEDIN_PROFILE_NAME")

    if not (linkedin_username and linkedin_password and linkedin_profile_name):
        raise LinkedinToolException("You need to set the LINKEDIN_EMAIL, LINKEDIN_PASSWORD, and LINKEDIN_PROFILE_NAME env variables")

    # Set up Chrome options
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")  # Commented out to see the browser

    # Set up the WebDriver using webdriver_manager
    service = Service(ChromeDriverManager().install())
    browser = webdriver.Chrome(service=service, options=chrome_options)

    try:
        print("Navigating to LinkedIn login page...")
        browser.get("https://www.linkedin.com/login")
        time.sleep(5)  # Wait for page to load

        print("Current URL:", browser.current_url)
        print("Page title:", browser.title)

        # Wait for the username field to be visible and interact with it
        print("Attempting to find username field...")
        username_input = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        username_input.send_keys(linkedin_username)
        print("Username entered")

        password_input = browser.find_element(By.ID, "password")
        password_input.send_keys(linkedin_password)
        password_input.send_keys(Keys.RETURN)
        print("Password entered and form submitted")

        # Wait for login to complete
        print("Waiting for login to complete...")
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.ID, "global-nav"))
        )
        print("Logged in successfully")

        print(f"Navigating to profile: {linkedin_profile_name}")
        browser.get(f"https://www.linkedin.com/in/{linkedin_profile_name}/recent-activity/all/")
        time.sleep(5)  # Wait for page to load

        print("Current URL after navigation:", browser.current_url)
        print("Page title after navigation:", browser.title)

        # Wait for the posts to load
        print("Waiting for posts to load...")
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "feed-shared-update-v2"))
        )

        print("Scrolling page...")
        for _ in range(2):
            browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        print("Extracting posts...")
        posts = get_linkedin_posts(browser.page_source)
        print(f"Number of posts extracted: {len(posts)}")
        return posts[:2]  # Return 2 of the latest posts

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Current URL:", browser.current_url)
        print("Page source:", browser.page_source)
        return []

    finally:
        print("Closing browser...")
        browser.quit()

if __name__ == "__main__":
    try:
        scraped_posts = scrape_linkedin_posts()
        print("\nScraped LinkedIn Posts:")
        for i, post in enumerate(scraped_posts, 1):
            print(f"\nPost {i}:\n{post}\n{'='*50}")
        if not scraped_posts:
            print("No posts were scraped.")
    except LinkedinToolException as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")