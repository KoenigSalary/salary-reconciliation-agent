"""
RMS Portal Automation Module
Handles login and file downloads from RMS portal
"""

import time
import logging
from config import Config

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
    WebDriverException
)

logger = logging.getLogger(__name__)


class RMSAutomation:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.download_dir = str(Config.DOWNLOAD_DIR)  # must be string for Chrome prefs

    def setup_driver(self):
        """Initialize Chrome driver with download preferences"""
        chrome_options = Options()

        # If RMS behaves weird in headless, comment this line and run visible browser
        chrome_options.add_argument("--headless=new")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")

        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)

        self.driver = webdriver.Chrome(options=chrome_options)

        # IMPORTANT: timeouts BEFORE heavy navigation
        self.driver.set_page_load_timeout(300)
        self.driver.set_script_timeout(300)

        self.wait = WebDriverWait(self.driver, 40)
        logger.info("Chrome driver initialized successfully")

    def safe_get(self, url, wait_css=None, timeout=60, retries=2):
        """
        More reliable than driver.get()+sleep:
        - retries if chromedriver/page load glitches
        - optionally waits for a CSS selector to appear
        """
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                self.driver.get(url)
                if wait_css:
                    WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_css))
                    )
                return
            except (TimeoutException, WebDriverException) as e:
                last_err = e
                if attempt == retries:
                    raise
                time.sleep(3)
        raise last_err

    def wait_dropdown_has_options(self, select_id, min_options=2, timeout=40):
        """
        Wait until a <select> has at least `min_options` <option>.
        RMS often populates dropdown via AJAX/postback.
        """
        def _has_options(driver):
            el = driver.find_element(By.ID, select_id)
            opts = el.find_elements(By.TAG_NAME, "option")
            return len(opts) >= min_options

        WebDriverWait(self.driver, timeout).until(_has_options)

    def login(self):
        """Login to RMS portal"""
        try:
            logger.info(f"Navigating to RMS portal: {Config.RMS_URL}")
            self.driver.get(Config.RMS_URL)

            username_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "txtUser"))
            )
            username_field.clear()
            username_field.send_keys(Config.RMS_USERNAME)

            password_field = self.driver.find_element(By.ID, "txtPwd")
            password_field.clear()
            password_field.send_keys(Config.RMS_PASSWORD)

            submit_button = self.driver.find_element(By.ID, "btnSubmit")
            submit_button.click()

            time.sleep(5)
            logger.info("Successfully logged in to RMS portal")
            return True

        except Exception as e:
            logger.error(f"Login failed: {str(e)}", exc_info=True)
            return False

    def download_salary_sheet(self, month_value):
        """
        Download salary sheet from Auto TDS panel
        month_value format example: "12/1/2025 12:00:00 AM"
        """
        try:
            logger.info("Navigating to Auto TDS panel")

            auto_tds_url = f"{Config.RMS_URL}/Accounts/AutoTDS.aspx"
            self.safe_get(auto_tds_url, wait_css="body", timeout=60)

            radio_button = self.wait.until(
                EC.presence_of_element_located((By.ID, "cphMainContent_mainContent_ddlsalarysheet_0"))
            )
            if not radio_button.is_selected():
                radio_button.click()

            month_dropdown = Select(
                self.wait.until(EC.presence_of_element_located(
                    (By.ID, "cphMainContent_mainContent_ddlsalarymonth")
                ))
            )
            month_dropdown.select_by_value(month_value)
            logger.info(f"Selected month: {month_value}")

            emp_type_dropdown = Select(
                self.wait.until(EC.presence_of_element_located(
                    (By.ID, "cphMainContent_mainContent_ddlEmpType")
                ))
            )
            emp_type_dropdown.select_by_value("2")
            logger.info("Selected Employee Type: Koenig")

            export_button = self.wait.until(
                EC.element_to_be_clickable((By.ID, "cphMainContent_mainContent_btndownloadSalarysheet"))
            )
            export_button.click()

            time.sleep(10)
            logger.info("Salary sheet downloaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to download salary sheet: {str(e)}", exc_info=True)
            return False

    def download_tds_sheet(self, month_value):
        """
        Download TDS sheet from Update TDS panel
        month_value format example: "12/1/2025 12:00:00 AM"
        """
        try:
            logger.info("Navigating to Update TDS panel")

            update_tds_url = f"{Config.RMS_URL}/HR/UpdateTDS.aspx"
            self.safe_get(update_tds_url, wait_css="body", timeout=60)

            # IMPORTANT: wait until options are actually populated
            self.wait_dropdown_has_options("ddlSearchMonth", min_options=2, timeout=40)

            month_dropdown = Select(self.driver.find_element(By.ID, "ddlSearchMonth"))
            opts = [(o.text.strip(), (o.get_attribute("value") or "").strip()) for o in month_dropdown.options]
            logger.info(f"TDS ddlSearchMonth options (text,value): {opts}")

            selected = False

            # Try select by VALUE first (if RMS uses date values)
            try:
                month_dropdown.select_by_value(month_value)
                selected = True
                logger.info(f"Selected TDS month by value: {month_value}")
            except Exception:
                pass

            # If not by value, select by visible month name/year
            if not selected:
                target_month_num = month_value.split("/")[0].strip()  # "12"
                target_year = month_value.split("/")[2].split(" ")[0].strip()  # "2025"

                month_names = {
                    "01": "January", "1": "January",
                    "02": "February", "2": "February",
                    "03": "March", "3": "March",
                    "04": "April", "4": "April",
                    "05": "May", "5": "May",
                    "06": "June", "6": "June",
                    "07": "July", "7": "July",
                    "08": "August", "8": "August",
                    "09": "September", "9": "September",
                    "10": "October",
                    "11": "November",
                    "12": "December",
                }
                target_month_name = month_names.get(target_month_num, "")

                if target_month_name:
                    for opt in month_dropdown.options:
                        txt = opt.text.strip()
                        if (target_month_name.lower() in txt.lower()) and (target_year in txt):
                            month_dropdown.select_by_visible_text(txt)
                            selected = True
                            logger.info(f"Selected TDS month by text: {txt}")
                            break

            # Final fallback: match 12 and 2025 anywhere in value/text
            if not selected:
                target_month_num = month_value.split("/")[0].strip()
                target_year = month_value.split("/")[2].split(" ")[0].strip()
                for opt in month_dropdown.options:
                    val = (opt.get_attribute("value") or "").strip()
                    txt = opt.text.strip()
                    if (target_year in val or target_year in txt) and (target_month_num in val or target_month_num in txt):
                        opt.click()
                        selected = True
                        logger.info(f"Selected TDS month by fallback: text='{txt}' value='{val}'")
                        break

            if not selected:
                raise Exception(f"Could not select TDS month. month_value='{month_value}'. Options were: {opts}")

            # Click Search button
            search_button = self.driver.find_element(By.ID, "btnFilter")
            search_button.click()

            time.sleep(5)

            excel_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'buttons-excel')]"))
            )
            excel_button.click()

            time.sleep(10)
            logger.info("TDS sheet downloaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to download TDS sheet: {str(e)}", exc_info=True)
            return False

    def download_bank_soa(self, start_date, end_date):
        """
        Download Bank Statement of Account from Bank Book Entry
        start_date/end_date format example: "01-Dec-25"
        """
        try:
            logger.info("Navigating to Bank Book Entry panel")

            bank_book_url = f"{Config.RMS_URL}/BankBook/BankBookEntry.aspx"
            self.safe_get(bank_book_url, wait_css="body", timeout=60)

            from_date_field = self.driver.find_element(By.ID, "cphMainContent_mainContent_txtDateFrom")
            from_date_field.clear()
            from_date_field.send_keys(start_date)
            logger.info(f"Set From Date: {start_date}")

            to_date_field = self.driver.find_element(By.ID, "cphMainContent_mainContent_txtDateTo")
            to_date_field.clear()
            to_date_field.send_keys(end_date)
            logger.info(f"Set To Date: {end_date}")

            acchead_dropdown = Select(self.driver.find_element(By.ID, "cphMainContent_mainContent_ddlAccHeadFilt"))
            acchead_dropdown.select_by_value("139")
            logger.info("Selected AccHead: Salary Exp-Payable")

            bank_dropdown = Select(self.driver.find_element(By.ID, "cphMainContent_mainContent_ddlBankSearch"))
            bank_dropdown.select_by_value("20")
            logger.info("Selected Bank: Kotak Delhi OD account 0317 KSPL")

            search_button = self.driver.find_element(By.ID, "cphMainContent_mainContent_btnSearch")
            search_button.click()

            time.sleep(5)

            select_all_checkbox = self.wait.until(
                EC.presence_of_element_located((By.ID, "cphMainContent_mainContent_grdv_ChkAll"))
            )
            if not select_all_checkbox.is_selected():
                select_all_checkbox.click()

            time.sleep(2)

            wait = WebDriverWait(self.driver, 40)

            # Wait for overlay to go away (RMS loader)
            try:
                wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.bg-overlay")))
            except Exception:
                pass

            export_id = "cphMainContent_mainContent_ExportToExcelSalaryUploaded"
            export_btn = wait.until(EC.element_to_be_clickable((By.ID, export_id)))

            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", export_btn)

            try:
                export_btn.click()
            except ElementClickInterceptedException:
                try:
                    wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.bg-overlay")))
                except Exception:
                    pass
                self.driver.execute_script("arguments[0].click();", export_btn)

            time.sleep(10)
            logger.info("Bank SOA downloaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to download Bank SOA: {str(e)}", exc_info=True)
            return False

    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")
