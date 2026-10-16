import urllib.request

FEED_URL = "https://www.btswholesaler.com/generatefeedbts?user_id=1429150&pass=Avedore556%2C&format=csv&language_code=en-GB"

print("STARTING DIAGNOSTIC TEST...")
req = urllib.request.Request(FEED_URL, headers={'User-Agent': 'Mozilla/5.0'})

try:
    with urllib.request.urlopen(req) as resp:
        text = resp.read().decode('utf-8', errors='ignore')
        lines = text.splitlines()
        print(f"TOTAL LINES FOUND: {len(lines)}")
        if len(lines) > 0:
            print("HEADER -->", lines[0][:200])
        if len(lines) > 1:
            print("ROW 1 -->", lines[1][:200])
except Exception as e:
    print("ERROR:", e)
