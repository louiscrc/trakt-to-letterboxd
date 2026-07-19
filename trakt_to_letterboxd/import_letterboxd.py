import contextlib
import os
import random
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

from . import console
from .config import Config
from .log import (
    configure_logging,
    ensure_letterboxd_window,
    log_err,
    log_heading,
    log_info,
    log_nav,
    log_ok,
    log_prompt,
    reset_browser_logs,
    set_browser_notify_driver,
)
from .paths import chrome_profile_dir, csv_path


def get_csv_path(filename: str) -> Path:
    return csv_path(filename)


EXPORT_CSV_HEADER = "Title,Year,Rating10,Rewatch,imdbID,WatchedDate\n"


def count_export_rows() -> int:
    export_path = get_csv_path("export.csv")
    if not export_path.exists():
        return 0
    with export_path.open() as f:
        return max(len(f.readlines()) - 1, 0)


def clear_export_csv() -> None:
    export_path = get_csv_path("export.csv")
    export_path.parent.mkdir(exist_ok=True)
    export_path.write_text(EXPORT_CSV_HEADER, encoding="utf-8")


def dismiss_cookie_consent(driver: webdriver.Chrome) -> bool:
    try:
        clicked = driver.execute_script("""
            const tryClick = (doc) => {
                const selectors = [
                    '.fc-cta-consent',
                    'button.fc-cta-consent',
                    '.fc-button-label',
                    'button[aria-label*="Accept all"]',
                    'button[aria-label*="Accept"]',
                    '.qc-cmp2-summary-buttons button[mode="primary"]',
                    'button[title*="Accept"]',
                ];
                for (const sel of selectors) {
                    const el = doc.querySelector(sel);
                    if (el) {
                        el.click();
                        return true;
                    }
                }
                return false;
            };
            if (tryClick(document)) return true;
            for (const iframe of document.querySelectorAll('iframe')) {
                try {
                    const doc = iframe.contentDocument;
                    if (doc && tryClick(doc)) return true;
                } catch (e) {}
            }
            return false;
        """)
        if clicked:
            time.sleep(1)
        return bool(clicked)
    except Exception:
        return False


def cookie_consent_visible(driver: webdriver.Chrome) -> bool:
    try:
        return bool(driver.execute_script("""
            const isVisible = (doc) => {
                const selectors = [
                    '.fc-dialog',
                    '.fc-consent-root',
                    '.qc-cmp2-container',
                    '[class*="cookie-consent"]',
                ];
                for (const sel of selectors) {
                    const el = doc.querySelector(sel);
                    if (!el) continue;
                    const style = doc.defaultView.getComputedStyle(el);
                    if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null) {
                        return true;
                    }
                }
                return false;
            };
            if (isVisible(document)) return true;
            for (const iframe of document.querySelectorAll('iframe')) {
                try {
                    if (iframe.contentDocument && isVisible(iframe.contentDocument)) return true;
                } catch (e) {}
            }
            return false;
        """))
    except Exception:
        return False


def is_cloudflare_challenge_page(driver: webdriver.Chrome) -> bool:
    try:
        return bool(driver.execute_script("""
            if (window._cf_chl_opt) return true;
            const markers = [
                'input[name="cf-turnstile-response"]',
                '[id^="cf-chl-widget"]',
                '#challenge-error-text',
                '#cf-wrapper',
                '#challenge-form',
                '#challenge-running',
                '#cf-challenge-running',
                'script[src*="challenge-platform"]',
                'script[src*="challenges.cloudflare.com/turnstile"]',
                '.ray-id',
                'a[href*="utm_source=challenge"]',
            ];
            if (markers.some((sel) => !!document.querySelector(sel))) return true;
            for (const iframe of document.querySelectorAll('iframe')) {
                if ((iframe.src || '').includes('challenges.cloudflare.com')) return true;
            }
            return false;
        """))
    except Exception:
        return False


def is_letterboxd_content_loaded(driver: webdriver.Chrome) -> bool:
    try:
        return bool(driver.execute_script("""
            return !!(
                document.querySelector('header#header, .site-header') ||
                document.querySelector('a[href="/films/"]') ||
                document.querySelector('#field-username') ||
                document.querySelector('form.js-sign-in-form')
            );
        """))
    except Exception:
        return False


def letterboxd_access_ready(driver: webdriver.Chrome) -> bool:
    return is_letterboxd_content_loaded(driver) and not cookie_consent_visible(driver)


def force_cloudflare_refresh(driver: webdriver.Chrome) -> None:
    """First Selenium navigation often soft-loads Letterboxd without Turnstile."""
    log_nav("Refreshing to trigger Cloudflare challenge…")
    ensure_letterboxd_window()
    driver.refresh()
    time.sleep(2)


def wait_for_letterboxd_access(
    driver: webdriver.Chrome,
    *,
    timeout: int = 300,
    require_turnstile: bool = False,
) -> bool:
    """Wait until Letterboxd is usable.

    When require_turnstile=True (post-refresh homepage check): if a Cloudflare
    challenge appears, wait for it; if the page loads with no challenge, treat
    Cloudflare as already validated.
    """
    deadline = time.time() + timeout
    turnstile_prompt_shown = False
    challenge_seen = False

    while time.time() < deadline:
        challenge_now = is_cloudflare_challenge_page(driver)
        if challenge_now:
            challenge_seen = True
            if not turnstile_prompt_shown:
                log_prompt("Please complete Cloudflare turnstile.")
                turnstile_prompt_shown = True
            time.sleep(2)
            continue

        if turnstile_prompt_shown:
            log_ok("Cloudflare challenge completed.")
            turnstile_prompt_shown = False

        if cookie_consent_visible(driver):
            if dismiss_cookie_consent(driver):
                log_nav("Cookie banner dismissed.")
            time.sleep(1)
            continue

        if not is_letterboxd_content_loaded(driver):
            time.sleep(1)
            continue

        if letterboxd_access_ready(driver):
            if require_turnstile and not challenge_seen:
                log_ok("Cloudflare validated.")
            return True

        time.sleep(1)

    log_err("Timed out waiting for page to load.")
    return False


def fill_sign_in_credentials(driver: webdriver.Chrome, config: Config) -> None:
    username_field = None
    for by, selector in (
        (By.ID, "field-username"),
        (By.CSS_SELECTOR, "form.js-sign-in-form input[name='username']"),
        (By.CSS_SELECTOR, "form.js-sign-in-form input[type='text']"),
    ):
        for field in driver.find_elements(by, selector):
            if field.is_displayed():
                username_field = field
                break
        if username_field:
            break
    if not username_field:
        raise TimeoutException("username field not found")

    password_field = None
    for by, selector in (
        (By.ID, "field-password"),
        (By.CSS_SELECTOR, "form.js-sign-in-form input[name='password']"),
        (By.CSS_SELECTOR, "form.js-sign-in-form input[type='password']"),
    ):
        for field in driver.find_elements(by, selector):
            if field.is_displayed():
                password_field = field
                break
        if password_field:
            break
    if not password_field:
        raise TimeoutException("password field not found")

    if config.letterboxd_username and not username_field.get_attribute("value"):
        username_field.clear()
        username_field.send_keys(config.letterboxd_username)
    if config.letterboxd_password and not password_field.get_attribute("value"):
        password_field.clear()
        password_field.send_keys(config.letterboxd_password)

    ensure_remember_me_checked(driver)
    password_field.click()


def ensure_remember_me_checked(driver: webdriver.Chrome) -> None:
    for selector in ("input.js-remember", "input[name='remember']"):
        for checkbox in driver.find_elements(By.CSS_SELECTOR, selector):
            if checkbox.is_selected():
                return
            checkbox_id = checkbox.get_attribute("id")
            if checkbox_id:
                labels = driver.find_elements(By.CSS_SELECTOR, f'label[for="{checkbox_id}"]')
                if labels:
                    labels[0].click()
                    return
            checkbox.click()
            return


def bootstrap_sign_in_form(driver: webdriver.Chrome) -> None:
    driver.execute_script("""
        document.dispatchEvent(new CustomEvent('sign-in.formready', { bubbles: true, cancelable: false }));
    """)
    time.sleep(2)


def hide_ad_overlays(driver: webdriver.Chrome) -> None:
    driver.execute_script("""
        var bottomRail = document.getElementById('pw-oop-bottom_rail');
        if (bottomRail) bottomRail.style.display = 'none';
        var ads = document.querySelectorAll('[id^="pw-oop-"], .pw-tag, .pw-corner-ad-video');
        ads.forEach(function(ad) { ad.style.display = 'none'; });
        var playwireAds = document.querySelectorAll('[alt*="Playwire"]');
        playwireAds.forEach(function(ad) {
            if (ad.parentElement) ad.parentElement.style.display = 'none';
        });
    """)


def is_letterboxd_logged_in(driver: webdriver.Chrome) -> bool:
    try:
        return bool(driver.execute_script("return window.person?.loggedIn === true"))
    except Exception:
        return False


def get_browser_profile_dir() -> Path:
    return chrome_profile_dir()

def prepare_homepage(driver: webdriver.Chrome, timeout: int = 300) -> bool:
    log_heading("Homepage")
    log_nav("Navigating to https://letterboxd.com/")
    ensure_letterboxd_window()
    driver.get("https://letterboxd.com/")
    time.sleep(0.5)
    # Drop previous-run overlay lines stored in letterboxd.com localStorage.
    reset_browser_logs()
    log_info("Checking Cloudflare validation…")
    time.sleep(1.0)
    ensure_letterboxd_window()

    # Never treat signed-in or cf_clearance as proof CF is valid — the cookie/session
    # can be expired or rejected. Always attempt to surface a challenge via refresh.
    force_cloudflare_refresh(driver)
    return wait_for_letterboxd_access(
        driver, timeout=timeout, require_turnstile=True
    )


def find_sign_in_submit(driver: webdriver.Chrome):
    selectors = (
        "form.js-sign-in-form input[type='submit']",
        "form.js-sign-in-form button[type='submit']",
        "form.js-signin input[type='submit']",
        "input.button[type='submit']",
        "button.button[type='submit']",
    )
    for selector in selectors:
        for el in driver.find_elements(By.CSS_SELECTOR, selector):
            if el.is_displayed() and el.is_enabled():
                return el
    # Fallback: any visible submit inside a form on the sign-in page
    for el in driver.find_elements(By.CSS_SELECTOR, "form input[type='submit'], form button[type='submit']"):
        if el.is_displayed() and el.is_enabled():
            return el
    return None


def click_sign_in_submit(driver: webdriver.Chrome) -> bool:
    """Human-like move + click on Sign In (avoids JS click which Letterboxd flags)."""
    button = find_sign_in_submit(driver)
    if button is None:
        log_err("Sign In button not found.")
        return False
    hide_ad_overlays(driver)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
    time.sleep(random.uniform(0.35, 0.9))
    try:
        ActionChains(driver).move_to_element(button).pause(random.uniform(0.2, 0.6)).click(button).perform()
    except Exception:
        try:
            button.click()
        except Exception as e:
            log_err(f"Could not click Sign In: {e}")
            return False
    return True


def wait_for_sign_in(
    driver: webdriver.Chrome,
    config: Config,
    timeout: int = 300,
    *,
    auto_sign_in: bool = True,
) -> bool:
    log_heading("Sign in")

    if is_letterboxd_logged_in(driver):
        log_ok("Already signed in.")
        return True

    log_nav("Navigating to https://letterboxd.com/sign-in/")
    ensure_letterboxd_window()
    driver.get("https://letterboxd.com/sign-in/")
    time.sleep(2)
    if not wait_for_letterboxd_access(driver, timeout=timeout):
        return False

    log_nav("Pre-filling credentials…")
    bootstrap_sign_in_form(driver)

    try:
        WebDriverWait(driver, 15).until(
            lambda d: any(
                d.find_elements(By.CSS_SELECTOR, sel)
                for sel in ("#field-username", "form.js-sign-in-form input[name='username']")
            )
        )
        fill_sign_in_credentials(driver, config)
    except TimeoutException:
        log_err("Could not find sign-in form.")
        return False

    if auto_sign_in:
        time.sleep(random.uniform(0.4, 1.0))
        log_nav("Clicking Sign In…")
        if not click_sign_in_submit(driver):
            log_prompt("Click Sign In in the browser.")
        else:
            log_nav("Sign In clicked — waiting for session…")
    else:
        log_prompt("Click Sign In in the browser.")

    deadline = time.time() + timeout
    prompted_403 = False
    while time.time() < deadline:
        if is_letterboxd_logged_in(driver):
            username = (
                driver.execute_script("return window.person?.username")
                or config.letterboxd_username
            )
            log_ok(f"Signed in as {username}.")
            return True

        if page_has_403_error(driver) and not prompted_403:
            log_prompt("Sign-in blocked — complete any captcha, then click Sign In manually.")
            prompted_403 = True

        time.sleep(1)

    log_err("Timed out waiting for sign-in.")
    return False


def page_has_403_error(driver: webdriver.Chrome) -> bool:
    try:
        return "403" in driver.execute_script("return document.body?.innerText || ''")
    except Exception:
        return False


def shutdown_driver(driver: webdriver.Chrome | None) -> None:
    if driver is None:
        return
    with contextlib.suppress(Exception):
        driver.quit()
    with contextlib.suppress(Exception):
        service = getattr(driver, "service", None)
        if service and service.process:
            service.process.kill()


def setup_driver() -> webdriver.Chrome:
    options = ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-data-dir={get_browser_profile_dir().resolve()}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})

    chrome_bin = os.getenv("CHROME_BIN")
    if chrome_bin:
        options.binary_location = chrome_bin

    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
    if chromedriver_path and Path(chromedriver_path).exists():
        service = ChromeService(executable_path=chromedriver_path)
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = ChromeService(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(0)
    # Reduce navigator.webdriver fingerprint (helps a bit with bot checks).
    with contextlib.suppress(Exception):
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                """
            },
        )
    return driver


def set_diary_import_option(driver: webdriver.Chrome, enabled: bool) -> None:
    checkbox = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "add-watchedDates-from-list"))
    )
    if checkbox.is_selected() == enabled:
        return
    driver.find_element(By.CSS_SELECTOR, 'label[for="add-watchedDates-from-list"]').click()
    time.sleep(0.3)
    log_nav("Diary entries from watched dates " + ("enabled" if enabled else "disabled") + ".")


def wait_for_import_review_button(driver: webdriver.Chrome, timeout: int = 120):
    """Wait until CSV matching finishes and the Import Films button is ready."""

    def review_ready(d: webdriver.Chrome):
        if "/import/csv" not in d.current_url:
            return False
        for button in d.find_elements(By.CSS_SELECTOR, "div.import-buttons a.submit-matched-films, a.submit-matched-films"):
            if not button.is_displayed():
                continue
            size = button.rect
            if size.get("width", 0) > 0 and size.get("height", 0) > 0:
                return button
        return False

    return WebDriverWait(driver, timeout).until(review_ready)


def click_import_films_button(driver: webdriver.Chrome, button) -> None:
    hide_ad_overlays(driver)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
    time.sleep(0.5)
    try:
        ActionChains(driver).move_to_element(button).pause(0.2).click(button).perform()
    except Exception:
        driver.execute_script("arguments[0].click();", button)


SAVED_FILMS_CONFIRMATION = re.compile(r"Saved \d+ films?\.?", re.IGNORECASE)


def get_import_confirmation_message(driver: webdriver.Chrome) -> str | None:
    for element in driver.find_elements(
        By.CSS_SELECTOR, "section#diary-importer-identifier strong"
    ):
        text = (element.text or "").strip()
        if SAVED_FILMS_CONFIRMATION.search(text):
            return text
    return None


def wait_for_dry_run_exit() -> None:
    log_prompt("Dry run — review import in the browser. Press Ctrl-C when done.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log_nav("Dry run stopped.")


def upload_csv_to_letterboxd(
    driver: webdriver.Chrome,
    csv_file_path: Path,
    row_count: int,
    *,
    diary: bool = True,
    dry_run: bool = False,
) -> bool:
    log_heading("Upload")
    log_nav(f"Uploading {row_count} row(s) from {csv_file_path.name}…")

    try:
        log_nav("Navigating to https://letterboxd.com/import/")
        ensure_letterboxd_window()
        driver.get("https://letterboxd.com/import/")
        time.sleep(3)

        if "sign-in" in driver.current_url:
            log_err("Not logged in — redirected to sign-in.")
            return False

        dismiss_cookie_consent(driver)

        log_nav("Selecting CSV file…")
        file_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        file_input.send_keys(str(csv_file_path.absolute()))

        log_nav("Waiting for film matching on /import/csv/…")
        try:
            import_button = wait_for_import_review_button(driver)
        except TimeoutException:
            log_err("Import Films button not found — matching may still be running.")
            return False

        set_diary_import_option(driver, diary)

        if dry_run:
            wait_for_dry_run_exit()
            return True

        log_nav("Clicking Import Films…")
        click_import_films_button(driver, import_button)

        log_nav("Waiting for import confirmation…")
        try:
            message = WebDriverWait(driver, 60).until(get_import_confirmation_message)
            log_ok(message)
            return True
        except TimeoutException:
            log_prompt("Import may not have completed — check Letterboxd.")
            return False

    except TimeoutException:
        log_err("Timed out during upload.")
        return False
    except Exception as e:
        log_err(f"Upload failed: {e}")
        return False


def upload_to_letterboxd(
    config: Config,
    *,
    diary: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
    auto_sign_in: bool = True,
) -> bool:
    configure_logging(verbose=verbose)
    row_count = count_export_rows()
    if row_count == 0:
        log_prompt("export.csv is empty — run `ttl trakt` first.")
        return True

    title = "Letterboxd upload (dry run)" if dry_run else "Letterboxd upload"
    log_info(title)
    log_nav(f"{row_count} row(s) in export.csv")

    driver = None
    try:
        log_nav("Starting Chrome…")
        driver = setup_driver()
        set_browser_notify_driver(driver)

        if not prepare_homepage(driver):
            return False

        if not wait_for_sign_in(driver, config, auto_sign_in=auto_sign_in):
            return False

        export_file = get_csv_path("export.csv")
        if not upload_csv_to_letterboxd(driver, export_file, row_count, diary=diary, dry_run=dry_run):
            return False

        if dry_run:
            log_ok("Letterboxd dry run done. Closing browser…")
            return True

        clear_export_csv()
        log_ok("export.csv cleared.")
        log_ok("Letterboxd upload done.")
        return True

    except KeyboardInterrupt:
        # Detach browser logging first — Selenium may already be dead after Ctrl-C.
        set_browser_notify_driver(None)
        console.print("  Interrupted.", style="yellow")
        return False
    except Exception as e:
        log_err(f"Letterboxd upload failed: {e}")
        return False
    finally:
        set_browser_notify_driver(None)
        shutdown_driver(driver)
