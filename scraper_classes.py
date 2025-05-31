import json
import time
import urllib.parse
import os
import requests
from bs4 import BeautifulSoup
from colorama import Fore, Style
import re # For regex in selectors

# HTTP Headers:
DEFAULT_HEADERS_BING = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9,en-GB;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Referer": "https://www.bing.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0"
}

class RequestsFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS_BING)
        self.last_response_content = None
        self.is_tor_fetcher = False

    def change_tor_identity(self):
        return True

    def get_current_ip(self, log_errors=True):
        try:
            response = self.session.get('https://httpbin.org/ip', timeout=10)
            self.last_response_content = response.text
            ip_address = response.json().get('origin')
            return ip_address if ip_address else "N/A (local)"
        except Exception:
            return "N/A (local)"

    def get(self, url, **kwargs):
        self.last_response_content = None
        try:
            timeout = kwargs.pop('timeout', 20)
            response = self.session.get(url, timeout=timeout, **kwargs)
            self.last_response_content = response.text
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                return e.response
            return None
        except Exception:
            return None

class BingShopScraper:
    def __init__(self, search_term, fetcher_instance=None, page_retry_attempts=3):
        self.search_term = search_term.strip()
        self.fetcher = fetcher_instance if fetcher_instance else RequestsFetcher()
        self.page_retry_attempts = page_retry_attempts
        self.base_url = "https://www.bing.com"
        self.shop_url_base = "https://www.bing.com/shop"
        self.is_using_tor_fetcher = getattr(self.fetcher, 'is_tor_fetcher', False)

        if not os.path.exists("out"):
            os.makedirs("out")

    def build_url(self):
        return f"{self.shop_url_base}?q={urllib.parse.quote_plus(self.search_term)}&cc=us&first=1"

    def _attempt_ip_change_if_tor(self):
        if not self.is_using_tor_fetcher:
            return True
        return self.fetcher.change_tor_identity()

    def extract_product_info_from_page(self):
        target_url = self.build_url()
        products_on_page = []

        response = self.fetcher.get(target_url)

        if not response:
            print(Fore.RED + f"[{self.search_term}] No response object for search term ({target_url}).")
            return products_on_page
        if not response.text:
            print(Fore.RED + f"[{self.search_term}] Empty response content for search term ({target_url}). Status: {response.status_code if hasattr(response, 'status_code') else 'N/A'}")
            return products_on_page
        if response.status_code == 404:
            print(Fore.RED + f"[{self.search_term}] Page for search term returned 404. Skipping.")
            return products_on_page

        soup = BeautifulSoup(response.text, "lxml")

        product_card_selectors = [
            "li.GridItem", "div.br-resultsItemObsRV", "div.sh-dlr__list-result",
            "div.sh-dgr__grprod", "div.br-card", "div.Card", "div.algocore",
            "div.product-item", "div[data-hveid]", "div[data-listing-id]"
        ]
        
        product_cards = []
        for selector in product_card_selectors:
            found_cards = soup.select(selector)
            if found_cards:
                product_cards.extend(found_cards)
        
        unique_product_cards = list(dict.fromkeys(product_cards))

        if not unique_product_cards:
            print(Fore.YELLOW + f"[{self.search_term}] No product card containers found using common selectors on page ({target_url}).")
            return products_on_page

        for card in unique_product_cards:
            # Removed "image_url" from here
            product_data = {
                "title": "N/A", "price": "N/A", "link": "N/A",
                "store": "N/A"
            }

            title_container = card.find('div', class_=lambda c: c and 'br-title' in c.split() and 'br-freeGridFontChange' in c.split())
            if title_container:
                title_span = title_container.find('span', title=True)
                if title_span:
                    product_data["title"] = title_span.get_text(strip=True)
                else:
                    product_data["title"] = title_container.get_text(strip=True)
            
            price_outer_container = card.find('div', class_=lambda c: c and 'pd-price' in c.split())
            if price_outer_container:
                price_inner_div = price_outer_container.find('div', class_='resp-one-line')
                if price_inner_div:
                    product_data["price"] = price_inner_div.get_text(strip=True)
                else:
                    product_data["price"] = price_outer_container.get_text(strip=True)
            
            link_tag = None
            if card.name == 'a' and card.has_attr('href'):
                link_tag = card
            else:
                if title_container and title_container.find_parent('a', href=True):
                    link_tag = title_container.find_parent('a', href=True)
                elif card.find('h3') and card.find('h3').find_parent('a', href=True):
                     link_tag = card.find('h3').find_parent('a', href=True)
                if not link_tag:
                    link_tag = card.find('a', href=True)
            
            if link_tag and link_tag.has_attr('href'):
                product_data["link"] = link_tag['href']

            # Image URL Extraction Logic REMOVED
            # image_tag = card.find('img', class_=re.compile(r'(img|image|thumb)', re.I))
            # if image_tag:
            #     product_data["image_url"] = image_tag.get('src') or image_tag.get('data-src')

            # Store Name Extraction
            product_data["store"] = "N/A" 
            store_seller_name_div = card.find('div', class_=lambda c: c and 'br-sellerName' in c.split())
            if store_seller_name_div:
                actual_seller_div = store_seller_name_div.find('div', class_='br-seller')
                if actual_seller_div:
                    product_data["store"] = actual_seller_div.get_text(strip=True)

            if product_data["store"] == "N/A": 
                store_tag_merchant = card.find(['a', 'div', 'span'], class_=['br-merchantName', re.compile(r'merchant', re.I)])
                if store_tag_merchant:
                    product_data["store"] = store_tag_merchant.get_text(strip=True)
            
            if product_data["store"] == "N/A": 
                store_from_tag = card.find('div', class_='br-pdFrom')
                if store_from_tag:
                    store_span = store_from_tag.find('span')
                    text_to_use = store_span.get_text(strip=True) if store_span else store_from_tag.get_text(strip=True)
                    if text_to_use.lower().startswith("from "):
                        product_data["store"] = text_to_use[5:].strip()
                    else:
                        product_data["store"] = text_to_use
            
            if product_data["link"] and not product_data["link"].startswith(('http://', 'https://')):
                product_data["link"] = urllib.parse.urljoin(self.base_url, product_data["link"].strip())
            
            # Image URL Resolution Logic REMOVED
            # if product_data["image_url"] and not product_data["image_url"].startswith(('http://', 'https://')):
            #     product_data["image_url"] = urllib.parse.urljoin(self.base_url, product_data["image_url"].strip())

            if (product_data["title"] != "N/A" and product_data["title"].strip()) or \
               (product_data["link"] != "N/A" and product_data["link"].strip()):
                products_on_page.append(product_data)

        return products_on_page

    def scrape(self):
        all_products_data = []
        page_data = None

        for retry_attempt in range(self.page_retry_attempts + 1):
            if retry_attempt > 0:
                print(Fore.YELLOW + f"[{self.search_term}] Retrying search (Overall attempt {retry_attempt +1})...")
                if self.is_using_tor_fetcher:
                    if not self._attempt_ip_change_if_tor():
                        print(Fore.RED + f"[{self.search_term}] Failed IP change via Tor, stopping retries.")
                        break
                time.sleep(7 if self.is_using_tor_fetcher else 3)

            page_data = self.extract_product_info_from_page()
            if page_data:
                all_products_data.extend(page_data)
                break

            last_content = getattr(self.fetcher, 'last_response_content', None)
            if last_content and isinstance(last_content, str) and \
               ("captcha" in last_content.lower() or \
                "access denied" in last_content.lower() or \
                "blocked" in last_content.lower() or \
                "unable to process request" in last_content.lower()):
                print(Fore.YELLOW + f"[{self.search_term}] Possible block/CAPTCHA, retry {retry_attempt+1}/{self.page_retry_attempts}.")
                if not self.is_using_tor_fetcher:
                    print(Fore.YELLOW + f"[{self.search_term}] Not using Tor, breaking retries on block/CAPTCHA.")
                    break
            elif retry_attempt < self.page_retry_attempts and not page_data:
                print(Fore.YELLOW + f"[{self.search_term}] No data fetched on attempt {retry_attempt+1}. Retrying...")

            if retry_attempt == self.page_retry_attempts:
                print(Fore.RED + f"[{self.search_term}] Failed to fetch data after {self.page_retry_attempts +1} attempts.")
                break

        start_time_str = time.strftime("%Y%m%d-%H%M%S")
        filename_prefix = "".join(c if c.isalnum() else "_" for c in self.search_term)
        filename = f"out/{filename_prefix}_{start_time_str}.json"

        result = {
            "search_term_input": self.search_term,
            "timestamp": start_time_str,
            "product_count": len(all_products_data),
            "products": all_products_data
        }

        if all_products_data:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4, ensure_ascii=False)
        return result