import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:4173")
BROWSER = os.getenv("BROWSER", "chrome").lower()
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts/screenshots"))


def make_driver():
    if BROWSER == "chrome":
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1440,1000")
        return webdriver.Chrome(options=options)

    if BROWSER == "firefox":
        options = webdriver.FirefoxOptions()
        options.add_argument("-headless")
        return webdriver.Firefox(options=options)

    if BROWSER == "edge":
        options = webdriver.EdgeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
        return webdriver.Edge(options=options)

    raise ValueError(f"Unsupported BROWSER={BROWSER!r}")


@pytest.fixture(scope="session")
def frontend_ready():
    try:
        with urlopen(BASE_URL, timeout=5) as response:
            html = response.read().decode("utf-8", errors="replace")
    except (URLError, OSError, ValueError) as exc:
        pytest.fail(
            f"Frontend unavailable at {BASE_URL}: {exc}. "
            "Run npm run test:e2e to build, serve, and test automatically, "
            "or start npm run dev and set BASE_URL=http://127.0.0.1:5173.",
            pytrace=False,
        )
    if "DigiDARA" not in html:
        pytest.fail(f"BASE_URL={BASE_URL} is not serving the DigiDARA frontend.", pytrace=False)


@pytest.fixture()
def driver(frontend_ready):
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    drv = make_driver()
    try:
        drv.set_page_load_timeout(30)
        yield drv
    finally:
        drv.quit()


def save(driver, name: str):
    driver.save_screenshot(str(ARTIFACT_DIR / f"{BROWSER}-{name}.png"))


def test_digidara_login_page_loads(driver):
    driver.get(BASE_URL)
    wait = WebDriverWait(driver, 20)

    wait.until(EC.title_contains("DigiDARA"))
    overlay = wait.until(EC.visibility_of_element_located((By.ID, "loginOverlay")))
    assert overlay.is_displayed()

    # The overlay opens in login mode by default (see LoginOverlay.tsx).
    heading = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#loginOverlay h1")))
    assert heading.text == "Welcome back"

    google_button = driver.find_element(By.CSS_SELECTOR, "button.google-btn")
    assert "Continue with Google" in google_button.text

    save(driver, "login")


def test_login_signup_tabs_work(driver):
    driver.get(BASE_URL)
    wait = WebDriverWait(driver, 20)

    # Mode switching is a plain link in the ".login-switch" footer line, not
    # a tab bar — see LoginOverlay.tsx's "First time here?"/"Already have an
    # account?" copy.
    signup_link = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//p[contains(@class,'login-switch')]//button[normalize-space()='Sign up instead']"))
    )
    signup_link.click()
    wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "#loginOverlay h1"), "Create your account"))
    assert driver.find_element(By.CSS_SELECTOR, "#loginOverlay h1").text == "Create your account"
    save(driver, "signup")

    login_link = driver.find_element(
        By.XPATH, "//p[contains(@class,'login-switch')]//button[normalize-space()='Log in instead']"
    )
    login_link.click()
    wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "#loginOverlay h1"), "Welcome back"))


def test_mobile_viewport_renders(driver):
    driver.set_window_size(390, 844)
    driver.get(BASE_URL)
    wait = WebDriverWait(driver, 20)
    overlay = wait.until(EC.visibility_of_element_located((By.ID, "loginOverlay")))
    assert overlay.is_displayed()
    heading = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#loginOverlay h1")))
    assert heading.is_displayed()
    save(driver, "mobile")
