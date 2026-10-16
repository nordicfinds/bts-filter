import urllib.request

FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

print("Downloading master BTS feed...")
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
req = urllib.request.Request(FEED_URL, headers=headers)

try:
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8', errors='ignore')
        lines = content.splitlines()
        print(f"Total lines downloaded: {len(lines)}")
        if lines:
            print(f"--- HEADER ROW ---")
            print(lines[0])
            print(f"--- FIRST PRODUCT ROW ---")
            if len(lines) > 1:
                print(lines[1])
except Exception as e:
    print(f"Error downloading feed: {e}")
