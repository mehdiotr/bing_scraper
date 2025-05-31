import concurrent.futures
import os
import time
from scraper_classes import BingShopScraper, RequestsFetcher
from tor import TorIPChanger
from colorama import Fore, Style, init

init(autoreset=True)

# --- Configuration ---
CATEGORY_PATHS_FILE = "category_paths.txt" # Contains search terms
MAX_PAGES_PER_CATEGORY = 1 # Only scraping one page per search term
USE_TOR = True
TOR_CONTROL_PASSWORD = None

MAX_CONCURRENT_WORKERS = 3
BATCH_SIZE = 5
TOR_SOCKS_PORT = 9050
TOR_CONTROL_PORT = 9051

# --- Main Runner Script Logic ---
def load_search_terms(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(Fore.RED + f"File {file_path} not found!")
    with open(file_path, "r", encoding="utf-8") as f:
        terms = [line.strip() for line in f if line.strip()]
    if not terms:
        raise ValueError(Fore.RED + "Search terms file is empty!")
    return terms

def process_search_term(search_term_input):
    search_term = search_term_input
    
    thread_name = concurrent.futures.thread.threading.current_thread().name
    print(Fore.MAGENTA + f"Thread {thread_name}: Processing search term: {Style.BRIGHT}{search_term}{Style.RESET_ALL}" +
          Fore.MAGENTA + f" (Tor: {USE_TOR})")
    
    fetcher_instance = None
    if USE_TOR:
        fetcher_instance = TorIPChanger(
            tor_socks_port=TOR_SOCKS_PORT,
            tor_control_port=TOR_CONTROL_PORT,
            control_password=TOR_CONTROL_PASSWORD
        )
    else:
        fetcher_instance = RequestsFetcher()
    
    scraper = BingShopScraper(
        search_term=search_term,
        fetcher_instance=fetcher_instance,
        page_retry_attempts=15 # Increased retry attempts
    )
    result = scraper.scrape()
    return result

def main():
    if USE_TOR:
        try:
            import stem
        except ImportError:
            print(Fore.RED + Style.BRIGHT + "CRITICAL ERROR: The 'stem' library is required by tor.py but not found.")
            print(Fore.YELLOW + "Please install it: pip install stem")
            print(Fore.RED + "Scraping with Tor will not work. Exiting.")
            return

    try:
        search_terms_list = load_search_terms(CATEGORY_PATHS_FILE)
    except (FileNotFoundError, ValueError) as e:
        print(e)
        return

    total_terms = len(search_terms_list)
    print(Fore.BLUE + Style.BRIGHT + f"Total search terms to process: {total_terms}")
    print(Fore.BLUE + f"Batch size: {BATCH_SIZE}")
    print(Fore.BLUE + f"Max concurrent workers: {MAX_CONCURRENT_WORKERS}")
    print(Fore.BLUE + f"Using Tor: {USE_TOR}")
    if USE_TOR:
        print(Fore.BLUE + f"Tor SOCKS Port: {TOR_SOCKS_PORT}, Tor Control Port: {TOR_CONTROL_PORT}")
    print(Fore.CYAN + "-" * 40)

    for i in range(0, total_terms, BATCH_SIZE):
        batch_terms = search_terms_list[i:i+BATCH_SIZE]
        current_batch_num = i // BATCH_SIZE + 1
        total_batches = (total_terms + BATCH_SIZE - 1) // BATCH_SIZE
        print(Fore.CYAN + Style.BRIGHT + 
              f"\n--- Processing Batch {current_batch_num} of {total_batches} ({len(batch_terms)} terms) ---")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_WORKERS) as executor:
            future_to_term = {executor.submit(process_search_term, term): term for term in batch_terms}

            for future in concurrent.futures.as_completed(future_to_term):
                term = future_to_term[future]
                try:
                    result = future.result()
                    if result and result.get("products"):
                        filename_prefix_for_log = "".join(c if c.isalnum() else "_" for c in term)
                        print(Fore.GREEN + f"[{term}] Found {len(result['products'])} items. Saved to out/{filename_prefix_for_log}_{result['timestamp']}.json")
                    elif result and result.get("product_count") == 0:
                        print(Fore.YELLOW + f"[{term}] No items found.")
                    else:
                        print(Fore.YELLOW + f"[{term}] No items found or issue occurred.")
                except Exception as e:
                    print(Fore.RED + f"[{term}] Error during processing in thread: {e}")
        
        print(Fore.CYAN + Style.BRIGHT + f"--- Batch {current_batch_num} completed ---")
        if i + BATCH_SIZE < total_terms:
            print(Fore.BLUE + "Waiting a few seconds before next batch...")
            time.sleep(10) 

    print(Fore.GREEN + Style.BRIGHT + "\nAll search terms processed.")

if __name__ == "__main__":
    main()