import time
import logging
from datetime import datetime
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd

from config import DATABASE_PATH

logger = logging.getLogger(__name__)

class Scraper:
    def __init__(self):
        self.driver = None

    async def __aenter__(self):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        logger.info("WebDriver initialized.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed.")

    async def parse_products(self) -> pd.DataFrame:
        wait = WebDriverWait(self.driver, 20)
        self.driver.get('https://www.mealty.ru/')
        logger.info("Navigated to https://www.mealty.ru/")

        # Close advertisement if present
        try:
            close_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//a[@title="Закрыть"]')))
            close_button.click()
            logger.info("Реклама закрыта.")
        except TimeoutException:
            logger.info("Реклама не обнаружена или уже закрыта.")
        except Exception as e:
            logger.error(f"Ошибка при попытке закрыть рекламу: {e}")

        # Scroll to load all products
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            logger.info("Scrolling to load products.")

        # Find all product images
        product_images = self.driver.find_elements(By.XPATH, '//img[@data-fancybox-href="#popup-menu"]')
        products = []
        logger.info(f"Found {len(product_images)} products.")

        for index, image in enumerate(product_images, start=1):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView();", image)
                time.sleep(0.5)

                actions = ActionChains(self.driver)
                actions.move_to_element(image).click().perform()

                # Wait for modal
                modal = wait.until(EC.visibility_of_element_located((By.ID, 'popup-menu')))
                modal_html = modal.get_attribute('innerHTML')
                soup = BeautifulSoup(modal_html, 'html.parser')

                # Extract product details
                product = self.extract_product_details(soup)
                products.append(product)
                logger.info(f"Product #{index} processed: {product['name']}")

                # Close modal
                self.close_modal(wait, actions)
            except Exception as e:
                logger.error(f"Ошибка при обработке продукта #{index}: {e}")
                self.safe_close_modal(wait, actions)
                continue

        return pd.DataFrame(products)

    def extract_product_details(self, soup: BeautifulSoup) -> dict:
        def get_text(selector, attr=None, replace=None, convert=None):
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if replace:
                    for old, new in replace.items():
                        text = text.replace(old, new)
                if convert == 'float':
                    return float(text) if text else None
                return text
            return None

        name = get_text('div.meal-popup__name')
        weight = get_text('div.meal-popup__weight', replace={'г': '', ',': '.'}, convert='float')
        calories = get_text('div.meal-popup__calories__portion', replace={',': '.'}, convert='float')
        proteins_per_100g = get_text('div.meal-popup__proteins', replace={',': '.'}, convert='float')
        fats_per_100g = get_text('div.meal-popup__fats', replace={',': '.'}, convert='float')
        carbs_per_100g = get_text('div.meal-popup__carbohydrates', replace={',': '.'}, convert='float')
        price = get_text('span.meal-popup__price', replace={',': '.'}, convert='float')

        if None in [name, weight, calories, proteins_per_100g, fats_per_100g, carbs_per_100g, price]:
            raise ValueError("Необходимые данные отсутствуют или некорректны.")

        proteins = proteins_per_100g * weight / 100
        fats = fats_per_100g * weight / 100
        carbs = carbs_per_100g * weight / 100

        return {
            'name': name,
            'proteins': proteins,
            'fats': fats,
            'carbs': carbs,
            'calories': calories,
            'weight': weight,
            'price': price
        }

    def close_modal(self, wait: WebDriverWait, actions: ActionChains):
        try:
            close_modal_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//a[@title="Закрыть"]')))
            close_modal_button.click()
            logger.info("Модальное окно закрыто.")
        except Exception as e:
            logger.error(f"Не удалось закрыть модальное окно: {e}")
            actions.send_keys(Keys.ESCAPE).perform()
            time.sleep(1)

    def safe_close_modal(self, wait: WebDriverWait, actions: ActionChains):
        try:
            self.close_modal(wait, actions)
            wait.until(EC.invisibility_of_element_located((By.ID, 'popup-menu')))
        except TimeoutException:
            logger.warning("Модальное окно не закрылось вовремя.")
