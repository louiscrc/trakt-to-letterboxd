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
from webdriver_manager.chrome import ChromeDriverManager

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
    
    # Options communes pour la stabilité
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Désactiver les notifications
    prefs = {
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)
    
    # Use webdriver-manager to automatically manage ChromeDriver
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)
    
    return driver


def login_to_letterboxd(driver: webdriver.Chrome, username: str, password: str) -> bool:
    """Login to Letterboxd"""
    console.print(f"Logging in to Letterboxd as {username}...", style="blue")
    
    try:
        # Aller sur la page de connexion
        console.print("Navigating to sign-in page...", style="dim")
        driver.get("https://letterboxd.com/sign-in/")
        time.sleep(3)
        
        # Debug: afficher l'URL actuelle
        console.print(f"Current URL: {driver.current_url}", style="dim")
        
        # Attendre et remplir le champ username
        console.print("Looking for username field...", style="dim")
        username_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "field-username"))
        )
        console.print("Found username field", style="dim")
        username_field.clear()
        username_field.send_keys(username)
        
        # Attendre et remplir le champ password
        console.print("Looking for password field...", style="dim")
        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "field-password"))
        )
        console.print("Found password field", style="dim")
        password_field.clear()
        password_field.send_keys(password)
        
        # Trouver et cliquer sur le bouton de connexion
        console.print("Looking for submit button...", style="dim")
        
        try:
            submit_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            console.print(f"Found submit button", style="dim")
        except TimeoutException:
            console.print("Could not find submit button with any known selector", style="red")
            console.print("Page source snippet:", style="yellow")
            # Afficher un extrait du HTML pour déboguer
            page_source = driver.page_source[:1000]
            console.print(page_source, style="dim")
            return False
        
        submit_button.click()
        console.print("Clicked submit button", style="dim")
        
        # Attendre que la connexion soit effectuée
        time.sleep(4)
        
        # Vérifier si la connexion a réussi
        current_url = driver.current_url
        console.print(f"After login URL: {current_url}", style="dim")
        
        if "sign-in" in current_url:
            console.print("Login failed - still on sign-in page", style="red")
            console.print("Check your credentials or if there's a captcha", style="yellow")
            return False
        
        console.print("Successfully logged in to Letterboxd", style="green")
        return True
        
    except TimeoutException as e:
        console.print(f"Login timeout - could not find login fields: {e}", style="red")
        console.print("Try running without --headless to see what's happening", style="yellow")
        return False
    except Exception as e:
        console.print(f"Login error: {e}", style="red")
        console.print("Try running without --headless to see what's happening", style="yellow")
        return False


def upload_csv_to_letterboxd(driver: webdriver.Chrome, csv_file_path: Path) -> bool:
    """Upload CSV file to Letterboxd import page"""
    console.print(f"Uploading {csv_file_path.name} to Letterboxd...", style="blue")
    
    try:
        # Vérifier que le fichier existe
        if not csv_file_path.exists():
            console.print(f"CSV file not found: {csv_file_path}", style="red")
            return False
        
        # Vérifier que le fichier n'est pas vide (plus que juste l'en-tête)
        with open(csv_file_path, 'r') as f:
            lines = f.readlines()
            if len(lines) <= 1:
                console.print("CSV file is empty (no data rows), skipping import", style="yellow")
                console.print("This is normal if you have no new watches since last sync", style="dim")
                return True  # Retourner True car ce n'est pas une erreur
        
        console.print(f"CSV contains {len(lines) - 1} row(s) to import", style="dim")
        
        # Aller sur la page d'import
        console.print("Navigating to import page...", style="dim")
        driver.get("https://letterboxd.com/import/")
        time.sleep(3)
        
        # Trouver l'input file
        console.print("Looking for file input...", style="dim")
        file_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        
        # Upload le fichier
        absolute_path = str(csv_file_path.absolute())
        console.print(f"Uploading file: {absolute_path}", style="dim")
        file_input.send_keys(absolute_path)
        
        console.print("File uploaded, waiting for processing...", style="blue")
        time.sleep(4)
        
        # Chercher le bouton d'import (c'est un lien <a> avec la classe submit-matched-films)
        console.print("Looking for import button...", style="dim")
        
        try:
            import_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.submit-matched-films"))
            )
            console.print(f"Found import button", style="dim")
        except TimeoutException:
            console.print("Could not find import button", style="yellow")
            console.print("The file may need manual review on Letterboxd", style="yellow")
            console.print(f"Current URL: {driver.current_url}", style="dim")
            # Afficher un extrait de la page
            if "error" in driver.page_source.lower():
                console.print("⚠️  Error detected in page source", style="red")
            return False
        
        # Cliquer sur le bouton d'import
        import_button.click()
        console.print("Import button clicked, waiting for completion...", style="blue")
        time.sleep(5)
        
        # Vérifier si l'import a réussi
        current_url = driver.current_url
        console.print(f"Final URL: {current_url}", style="dim")
        
        if "complete" in driver.page_source.lower() or "success" in driver.page_source.lower():
            console.print("Import completed successfully!", style="green")
            return True
        elif "error" in driver.page_source.lower():
            console.print("Import may have failed, check Letterboxd", style="yellow")
            return False
        else:
            console.print("Import submitted, check Letterboxd to verify", style="yellow")
            return True
            
    except TimeoutException as e:
        console.print(f"Timeout while uploading file: {e}", style="red")
        return False
    except Exception as e:
        console.print(f"Upload error: {e}", style="red")
        return False


def import_to_letterboxd(account: Account, headless: bool = False) -> bool:
    """Main import function to upload export.csv to Letterboxd"""
    console.print(f"Starting import for Letterboxd account: {account.letterboxd_username}", style="purple4")
    
    # Vérifier que le mot de passe est configuré
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
        import_to_letterboxd(account, headless=False)
