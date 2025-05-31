import requests
from stem import Signal
from stem.control import Controller
import time
from colorama import Fore, Style, init

init(autoreset=True)

DEFAULT_HEADERS_BING_TOR = {
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

class TorIPChanger:
    DEFAULT_SOCKS_PORT = 9050
    DEFAULT_CONTROL_PORT = 9051

    def __init__(self, tor_socks_port=DEFAULT_SOCKS_PORT, tor_control_port=DEFAULT_CONTROL_PORT, control_password=None, custom_headers=None, new_ip_wait_time=15):
        self.proxies = {
            'http': f'socks5h://127.0.0.1:{tor_socks_port}',
            'https': f'socks5h://127.0.0.1:{tor_socks_port}'
        }
        self.control_port = tor_control_port
        self.control_password = control_password
        
        self.headers = DEFAULT_HEADERS_BING_TOR.copy()
        if custom_headers:
            self.headers.update(custom_headers)
        
        self.is_tor_fetcher = True
        self.last_response_content = None
        self.new_ip_wait_time = new_ip_wait_time

    def change_tor_identity(self):
        current_ip_before_change = self.get_current_ip(log_errors=False)
        try:
            with Controller.from_port(port=self.control_port) as controller:
                if self.control_password:
                    controller.authenticate(password=self.control_password)
                else:
                    controller.authenticate()
                controller.signal(Signal.NEWNYM)
                
                time_slept_total = 0
                ip_changed_detected = False
                iterations = max(1, self.new_ip_wait_time // 3) 

                for _ in range(iterations): 
                    sleep_duration = min(3, self.new_ip_wait_time - time_slept_total)
                    if sleep_duration <=0: break
                    time.sleep(sleep_duration)
                    time_slept_total += sleep_duration

                    new_ip_check = self.get_current_ip(log_errors=False)
                    if new_ip_check and new_ip_check != "IP Not Found" and new_ip_check != current_ip_before_change:
                        ip_changed_detected = True
                        return True 
                    if time_slept_total >= self.new_ip_wait_time: break
                
                if not ip_changed_detected:
                    final_new_ip = self.get_current_ip(log_errors=False)
                    return (final_new_ip and final_new_ip != "IP Not Found" and final_new_ip != current_ip_before_change) or \
                           (final_new_ip and final_new_ip != "IP Not Found")
                return True
        except Exception as e:
            print(Fore.RED + f"Error changing Tor identity: {e}")
            return False

    def get_current_ip(self, log_errors=True):
        self.last_response_content = None
        current_request_headers = self.headers.copy()
        try:
            response = requests.get('https://api.ipify.org?format=json', proxies=self.proxies, timeout=15, headers=current_request_headers)
            response.raise_for_status()
            self.last_response_content = response.text
            ip_address = response.json().get("ip")
            return ip_address if ip_address else "IP Not Found"
        except requests.exceptions.RequestException:
            return "IP Not Found"

    def get(self, url, timeout=25, custom_headers_for_request=None):
        self.last_response_content = None
        current_request_headers = self.headers.copy()
        if custom_headers_for_request:
            current_request_headers.update(custom_headers_for_request)
        
        try:
            response = requests.get(url, proxies=self.proxies, timeout=timeout, headers=current_request_headers)
            self.last_response_content = response.text
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                 return e.response 
            return None

    def post(self, url, data=None, json_payload=None, timeout=25, custom_headers_for_request=None):
        self.last_response_content = None
        current_request_headers = self.headers.copy()
        if custom_headers_for_request:
            current_request_headers.update(custom_headers_for_request)
        try:
            response = requests.post(url, proxies=self.proxies, timeout=timeout, headers=current_request_headers, data=data, json=json_payload)
            self.last_response_content = response.text
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                return e.response
            return None

if __name__ == "__main__":
    print(Fore.MAGENTA + Style.BRIGHT + "Testing TorIPChanger...")
    tor_changer = TorIPChanger(control_password=None) 

    print(Fore.CYAN + "Fetching initial IP...")
    initial_ip = tor_changer.get_current_ip()
    print(Fore.CYAN + f"Initial IP: {initial_ip if initial_ip != 'IP Not Found' else Fore.YELLOW + 'Failed to get initial IP'}")

    if initial_ip and initial_ip != "IP Not Found":
        print(Fore.BLUE + "\nAttempting to change IP address...")
        if tor_changer.change_tor_identity():
            print(Fore.GREEN + "IP change process attempted.")
            print(Fore.CYAN + "Fetching new IP...")
            new_ip = tor_changer.get_current_ip()
            print(Fore.CYAN + f"New IP: {new_ip if new_ip != 'IP Not Found' else Fore.YELLOW + 'Failed to get new IP'}")
            if initial_ip != new_ip and new_ip and new_ip != "IP Not Found":
                print(Fore.GREEN + Style.BRIGHT + "SUCCESS: IP address appears to have changed.")
            elif new_ip and new_ip != "IP Not Found":
                print(Fore.YELLOW + "NOTICE: IP address is the same or verification inconclusive.")
            else:
                print(Fore.RED + "FAILURE: Could not determine new IP address.")
        else:
            print(Fore.RED + "Failed to send NEWNYM signal or connect to Tor control port.")
    else:
        print(Fore.YELLOW + "Cannot proceed with IP change test as initial IP could not be determined.")

    print(Fore.BLUE + "\nTesting GET request through Tor...")
    test_get_url = "https://httpbin.org/headers"
    response_get = tor_changer.get(test_get_url)
    if response_get and response_get.status_code == 200:
        print(Fore.GREEN + f"GET request to {test_get_url} successful.")
    else:
        status = response_get.status_code if response_get else "None"
        print(Fore.RED + f"GET request to {test_get_url} failed. Status: {status}")

    print(Fore.BLUE + "\nTesting POST request through Tor...")
    test_post_url = "https://httpbin.org/post"
    response_post = tor_changer.post(test_post_url, json_payload={'key': 'value'})
    if response_post and response_post.status_code == 200:
        print(Fore.GREEN + f"POST request to {test_post_url} successful.")
    else:
        status = response_post.status_code if response_post else "None"
        print(Fore.RED + f"POST request to {test_post_url} failed. Status: {status}")