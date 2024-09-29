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
from langchain_groq import ChatGroq
from langchain.text_splitter import HTMLHeaderTextSplitter
from langchain.schema import Document
import random

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

def get_profile_info(page_source: str):
    linkedin_soup = BeautifulSoup(page_source, "lxml")
    profile_section = linkedin_soup.find("main", class_="scaffold-layout__main")
    
    if profile_section:
        profile_html = str(profile_section)
        return extract_profile_info_with_llm(profile_html)
    else:
        return {"error": "Profile section not found"}

def split_html_content(html_content: str):
    headers_to_split_on = [
        ("h1", "Header 1"),
        ("h2", "Header 2"),
        ("h3", "Header 3"),
        ("h4", "Header 4"),
        ("h5", "Header 5"),
        ("h6", "Header 6"),
    ]
    html_splitter = HTMLHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    html_splits = html_splitter.split_text(html_content)
    return html_splits

def extract_relevant_sections(profile_html: str):
    soup = BeautifulSoup(profile_html, 'html.parser')
    relevant_sections = []
    
    # Extract specific sections
    sections = ['profile-info', 'experience', 'education', 'skills']
    for section in sections:
        element = soup.find('section', {'id': section})
        if element:
            relevant_sections.append(str(element))
    
    return '\n'.join(relevant_sections)

def extract_profile_info_with_llm(profile_html: str):
    groq_api_key = "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"
    
    llm = ChatGroq(
        groq_api_key=groq_api_key,
        model_name="mixtral-8x7b-32768",
    )

    html_splits = split_html_content(profile_html)
    
    combined_content = ""
    for split in html_splits:
        combined_content += f"{split.metadata.get('Header 1', '')}\n"
        combined_content += f"{split.metadata.get('Header 2', '')}\n"
        combined_content += f"{split.metadata.get('Header 3', '')}\n"
        combined_content += f"{split.page_content}\n\n"

    prompt = f"""
    Given the following structured content from a LinkedIn profile, extract and summarize the following information:
    1. Name
    2. Headline
    3. About section
    4. Experience (including job titles and companies)
    5. Education
    6. Skills

    Present the information in a structured format. If any section is not found, indicate that it's not available.

    Profile content:
    {combined_content}
    """

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = llm.invoke(prompt)
            return response.content
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Error in LLM processing: {e}. Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Error in LLM processing after {max_retries} attempts: {e}")
                return f"Error: {str(e)}"

def save_profile_info_to_file(profile_info: str, filename: str = "linkedin_profile_info.txt"):
    with open(filename, "w", encoding="utf-8") as file:
        file.write(profile_info)
    print(f"Profile information saved to {filename}")

def scrape_linkedin_profile():
    linkedin_username = os.environ.get("LINKEDIN_EMAIL")
    linkedin_password = os.environ.get("LINKEDIN_PASSWORD")
    linkedin_profile_name = os.environ.get("LINKEDIN_PROFILE_NAME")

    if not (linkedin_username and linkedin_password and linkedin_profile_name):
        raise LinkedinToolException("You need to set the LINKEDIN_EMAIL, LINKEDIN_PASSWORD, and LINKEDIN_PROFILE_NAME env variables")

    # Set up Chrome options
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")  # Uncomment this line to run in headless mode

    # Set up the WebDriver using webdriver_manager
    service = Service(ChromeDriverManager().install())
    browser = webdriver.Chrome(service=service, options=chrome_options)

    try:
        print("Navigating to LinkedIn login page...")
        browser.get("https://www.linkedin.com/login")
        time.sleep(5)  # Wait for page to load

        # Check if we're on the login page
        if "login" not in browser.current_url:
            print("Redirected to join page. Attempting to navigate to login...")
            login_button = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Sign in"))
            )
            login_button.click()
            time.sleep(3)  # Wait for login page to load

        # Login process
        print("Logging in...")
        username_input = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        password_input = browser.find_element(By.ID, "password")
        
        username_input.send_keys(linkedin_username)
        password_input.send_keys(linkedin_password)
        password_input.send_keys(Keys.RETURN)
        time.sleep(5)  # Wait for login to complete

        print(f"Navigating to profile: {linkedin_profile_name}")
        browser.get(f"https://www.linkedin.com/in/{linkedin_profile_name}/")
        time.sleep(5)  # Wait for page to load

        print("Current URL after navigation:", browser.current_url)
        print("Page title after navigation:", browser.title)

        # Scroll the page to load all content
        print("Scrolling page...")
        for _ in range(3):
            browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        print("Extracting profile information...")
        profile_info = get_profile_info(browser.page_source)
        return profile_info

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Current URL:", browser.current_url)
        return {}

    finally:
        print("Closing browser...")
        browser.quit()

if __name__ == "__main__":
    try:
        profile_info = scrape_linkedin_profile()
        print("\nScraped LinkedIn Profile:")
        print(profile_info)
        
        # Save the profile information to a file
        save_profile_info_to_file(profile_info)
    except LinkedinToolException as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()