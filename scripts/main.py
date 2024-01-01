import hashlib
import json
import logging
import tempfile
import threading
import sys

import numpy
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import cv2
import numpy as np
from PIL import Image
from PIL import ImageCms
from PIL import ImageFile

import os
ImageFile.LOAD_TRUNCATED_IMAGES = True

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
UI_DIR = os.path.join(SCRIPT_DIR, "ui")
SRC_DIR = os.path.join(UI_DIR, "src")
ASSETS_DIR = os.path.join(SRC_DIR, "assets")
PRODUCTS_DIR = os.path.join(ASSETS_DIR, "products")
os.makedirs(PRODUCTS_DIR, exist_ok=True)

# URL to access
BASE_URL = "https://ksp.co.il/m_action/api/category/3605..6479?sort=5"




def save_image(url, file_path):
    with tempfile.NamedTemporaryFile() as f:
        with open(f.name, 'wb+') as _f:
            _f.write(requests.get(url).content)
            path = f.name
        image = cv2.imread(path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply thresholding - adjust the threshold value as needed
        _, thresh = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY)

        # Invert the thresholded image (if needed)
        thresh_inv = cv2.bitwise_not(thresh)

        # Find contours based on the inverted threshold
        contours, _ = cv2.findContours(thresh_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Create an all black mask the size of the image
        mask = np.zeros_like(image)

        # Fill the detected objects with white in the mask
        cv2.drawContours(mask, contours, -1, (255, 255, 255), thickness=cv2.FILLED)

        # Bitwise operation to keep only the objects and not the background
        result = cv2.bitwise_and(image, mask)

        # Convert mask to grayscale
        mask_gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

        # Create final image with transparent background
        final = np.dstack((result, mask_gray))
        file_path = file_path.replace(".jpg", ".png").replace(".jpeg", ".png")
        # save as png
        final = cv2.cvtColor(final, cv2.COLOR_BGR2RGB)
        cv2.imwrite(file_path, final)


def setup():
    chrome_options = Options()
    return webdriver.Chrome(options=chrome_options)


def get_items(url):
    driver = setup()
    driver.get(url)
    driver.implicitly_wait(10)
    items = driver.page_source
    driver.quit()
    return items


def get_legos():
    next = True
    all_results = []
    url = BASE_URL
    while next:
        items = get_items(url)
        soup = BeautifulSoup(items, 'html.parser')
        items = soup.text
        items = json.loads(items)
        items = items.get("result")
        all_results.append(items)
        if not items.get("next") or items.get("next") < next:
            break
        url = f"{BASE_URL}&page={items.get('next')}"
    return all_results


def main():
    if os.path.exists("__legos.json"):
        with open("__legos.json", "r") as f:
            items = json.load(f)
    else:
        items = get_legos()
        with open("legos.json", "w+") as f:
            json.dump(items, f, indent=4)
    legos = []
    ids = set()
    for item in items:
        _items = []

        for _item in item.get("items"):
            _id = hashlib.md5(f"{_item.get('name')}{item.get('uin')}{item.get('uinsql')}{item.get('img')}".encode()).hexdigest()
            if _id in ids:
                logging.info(f"Skipping duplicate item: {_id}")
                continue
            res = {}

            img_path = os.path.join(PRODUCTS_DIR, f"{_id}.jpg")
            img_ui_path = os.path.join("assets", "products", f"{_id}.jpg")
            save_image(_item.get("img"), img_path)

            res["id"] = _id
            price_per_piece = _item.get("price") / _item.get("kg")
            res["name"] = _item.get("name")
            res["price"] = _item.get("price")
            res["pieces"] = _item.get("kg")
            res["price_per_piece"] = price_per_piece
            populartity = _item.get("popularies_data", {}).get("count_of_clicks", -1)
            res["popularity"] = populartity
            res["ksp_url"] = f"https://ksp.co.il/web/item/{_item.get('uin')}"
            res["img_url"] = _item.get("img")
            res["img"] = img_ui_path
            res["tags"] = _item.get("tags")
            res["uin"] = _item.get("uin")
            res["uinsql"] = _item.get("uinsql")
            ids.add(_id)
            _items.append(res)
        legos.extend(_items)

    logging.info(f"Found {len(legos)} legos")
    for lego in legos:
        logging.info(f"Lego: {lego.get('name')}")
    with open("legos_items.json", "w+") as f:
        json.dump(legos, f, indent=4)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main()
