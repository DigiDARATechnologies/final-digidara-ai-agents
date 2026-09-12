import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
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


_CLICK_SWITCH_LINK_JS = """
const label = arguments[0];
const p = document.querySelector('.login-switch');
if (!p) return false;
const btn = Array.from(p.querySelectorAll('button')).find((b) => b.textContent.trim() === label);
if (!btn || btn.offsetParent === null) return false;
btn.click();
return true;
"""


def click_switch_link(driver, wait, label):
    """Poll for the ".login-switch" button with this exact text and click it
    in the same JS call, entirely bypassing Selenium's element-discovery and
    clickability machinery (find_element + EC.element_to_be_clickable +
    WebElement.click()).

    Selenium's own visibility/clickability checks (`is_displayed`,
    `is_enabled`, WebElement.text) have repeatedly lagged behind the real
    DOM on Firefox/geckodriver specifically in this suite -- see
    wait_for_heading below, root-caused the same way -- while a direct JS
    read of offsetParent/textContent has been reliable and immediate every
    time. Doing discovery, visibility, and the click itself all inside one
    execute_script call removes every layer that's shown this lag so far.
    """
    wait.until(lambda d: d.execute_script(_CLICK_SWITCH_LINK_JS, label))


def heading_text(driver):
    return driver.execute_script("return document.querySelector('#loginOverlay h1')?.textContent ?? ''")


def wait_for_heading(driver, wait, expected_text, debug_name):
    """Poll the heading's raw textContent via execute_script rather than
    Selenium's WebElement.text / EC.text_to_be_present_in_element.

    Root-caused via the diagnostics this replaced: after the click, the DOM
    already had the right heading (confirmed by reading textContent), but
    geckodriver's `.text` -- which computes a "rendered text" that accounts
    for visibility/layout, not a plain textContent read -- never reflected
    it within the wait window. Chrome and Edge don't have this quirk; only
    Firefox does. Reading textContent directly sidesteps that layer.
    """
    try:
        wait.until(lambda d: expected_text in heading_text(d))
    except TimeoutException:
        actual = heading_text(driver)
        switch_html = driver.execute_script("return document.querySelector('.login-switch')?.outerHTML")
        save(driver, debug_name)
        raise AssertionError(
            f"Heading never became {expected_text!r}. "
            f"Actual heading text: {actual!r}. "
            f".login-switch outerHTML: {switch_html!r}."
        )


def test_digidara_login_page_loads(driver):
    driver.get(BASE_URL)
    wait = WebDriverWait(driver, 20)

    wait.until(EC.title_contains("DigiDARA"))
    overlay = wait.until(EC.visibility_of_element_located((By.ID, "loginOverlay")))
    assert overlay.is_displayed()

    # The overlay opens in login mode by default (see LoginOverlay.tsx).
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#loginOverlay h1")))
    assert heading_text(driver) == "Welcome back"

    google_button = driver.find_element(By.CSS_SELECTOR, "button.google-btn")
    assert "Continue with Google" in google_button.text

    save(driver, "login")


def test_login_signup_tabs_work(driver):
    driver.get(BASE_URL)
    wait = WebDriverWait(driver, 20)

    # Mode switching is a plain link in the ".login-switch" footer line, not
    # a tab bar — see LoginOverlay.tsx's "First time here?"/"Already have an
    # account?" copy.
    click_switch_link(driver, wait, "Sign up instead")
    wait_for_heading(driver, wait, "Create your account", "signup-debug")
    assert heading_text(driver) == "Create your account"
    save(driver, "signup")

    click_switch_link(driver, wait, "Log in instead")
    wait_for_heading(driver, wait, "Welcome back", "login-debug")


def test_mobile_viewport_renders(driver):
    driver.set_window_size(390, 844)
    driver.get(BASE_URL)
    wait = WebDriverWait(driver, 20)
    overlay = wait.until(EC.visibility_of_element_located((By.ID, "loginOverlay")))
    assert overlay.is_displayed()
    heading = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#loginOverlay h1")))
    assert heading.is_displayed()
    save(driver, "mobile")
