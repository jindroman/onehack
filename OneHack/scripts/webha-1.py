import requests
from concurrent.futures import ThreadPoolExecutor

URL = input("napis url : ")
REQUESTS = int(input("kolik chces poslat requestu : "))
WORKERS = int(input("kolik chces poslat botu : "))

def make_request(i):
    try:
        print(f"Starting request {i}")
        r = requests.get(URL, timeout=2)
        print(f"{i}: {r.status_code}")
    except requests.exceptions.Timeout:
        print(f"{i}: timed out")
    except Exception as e:
        print(f"{i}: {e}")

with ThreadPoolExecutor(max_workers=WORKERS) as executor:
    executor.map(make_request, range(REQUESTS))