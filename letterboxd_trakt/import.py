import time
from pathlib import Path
from typing import Dict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

from . import console
from .config import Account, Config


def get_csv_path(filename: str) -> Path:
    """Get path for CSV file"""
    csv_path = Path("/csv") if Path("/csv").exists() else Path("./csv")
    return csv_path / filename


def setup_driver(headless: bool = False) -> webdriver.Chrome:
    """Configure and return a Chrome WebDriver"""
    console.print("Setting up Chrome WebDriver...", style="blue")
    
    options = ChromeOptions()
    
    if headless:
        options.add_argument("--headless=new")
    
    # Common options for stability
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Disable notifications
    prefs = {
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    
    return driver


def login_to_letterboxd(driver: webdriver.Chrome, username: str, password: str) -> bool:
    """Login to Letterboxd"""
    console.print(f"Logging in to Letterboxd as {username}...", style="blue")
    
    try:
        # Navigate to sign-in page
        driver.get("https://letterboxd.com/sign-in/")
        time.sleep(2)
        
        # Fill login form
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "field-username"))
        )
        password_field = driver.find_element(By.ID, "field-password")
        
        username_field.clear()
        username_field.send_keys(username)
        
        password_field.clear()
        password_field.send_keys(password)
        
        # Submit form
        submit_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
        submit_button.click()
        
        # Wait for login to complete
        time.sleep(3)
        
        # Check if login was successful
        if "sign-in" in driver.current_url:
            console.print("Login failed - still on sign-in page", style="red")
            return False
        
        console.print("Successfully logged in to Letterboxd", style="green")
        return True
        
    except TimeoutException:
        console.print("Login timeout - could not find login fields", style="red")
        return False
    except Exception as e:
        console.print(f"Login error: {e}", style="red")
        return False


def upload_csv_to_letterboxd(driver: webdriver.Chrome, csv_file_path: Path) -> bool:
    """Upload CSV file to Letterboxd import page"""
    console.print(f"Uploading {csv_file_path.name} to Letterboxd...", style="blue")
    
    try:
        # Check if file exists
        if not csv_file_path.exists():
            console.print(f"CSV file not found: {csv_file_path}", style="red")
            return False
        
        # Navigate to import page
        driver.get("https://letterboxd.com/import/")
        time.sleep(2)
        
        # Find file input
        file_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        
        # Upload the file
        absolute_path = str(csv_file_path.absolute())
        file_input.send_keys(absolute_path)
        
        console.print("File uploaded, waiting for processing...", style="blue")
        time.sleep(3)
        
        # Look for import button
        try:
            import_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit'][value='Import']"))
            )
            import_button.click()
            console.print("Import submitted!", style="green")
            time.sleep(5)
            
            # Check if import was successful
            if "import" in driver.current_url and "complete" in driver.page_source.lower():
                console.print("Import completed successfully!", style="green")
                return True
            else:
                console.print("Import may have completed, check Letterboxd", style="yellow")
                return True
                
        except TimeoutException:
            console.print("Could not find import button - file may need manual confirmation", style="yellow")
            return False
            
    except TimeoutException:
        console.print("Timeout while uploading file", style="red")
        return False
    except Exception as e:
        console.print(f"Upload error: {e}", style="red")
        return False


def import_to_letterboxd(account: Account, config: Config, headless: bool = False) -> bool:
    """Main import function to upload export.csv to Letterboxd"""
    console.print(f"Starting import for Letterboxd account: {account.letterboxd_username}", style="purple4")
    
    # Check if password is configured
    if not account.letterboxd_password:
        console.print("Letterboxd password not configured in config.yml", style="red")
        return False
    
    driver = None
    try:
        # Setup WebDriver
        driver = setup_driver(headless=headless)
        
        # Login
        if not login_to_letterboxd(driver, account.letterboxd_username, account.letterboxd_password):
            return False
        
        # Upload CSV
        csv_path = get_csv_path("export.csv")
        if not upload_csv_to_letterboxd(driver, csv_path):
            return False
        
        console.print("Import process completed!", style="purple4")
        return True
        
    except Exception as e:
        console.print(f"Import failed: {e}", style="red")
        return False
        
    finally:
        if driver:
            console.print("Closing browser...", style="blue")
            time.sleep(2)
            driver.quit()


if __name__ == "__main__":
    from .config import load_config
    
    config = load_config()
    if config and config.accounts:
        account = config.accounts[0]
        import_to_letterboxd(account, config, headless=False)
