import urllib.request
import json
import urllib.error
import ssl

ssl_context = ssl._create_unverified_context()

def test_cobalt():
    url = "https://api.cobalt.tools/"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Try different parameter names
    # Key properties:
    # - url: required
    # - downloadMode: "audio"
    body = {
        "url": "https://www.youtube.com/watch?v=eXkHvT--DBU",
        "downloadMode": "audio"
    }
    
    req = urllib.request.Request(url, headers=headers, data=json.dumps(body).encode())
    try:
        response = urllib.request.urlopen(req, context=ssl_context).read().decode()
        print("Success:", response)
    except urllib.error.HTTPError as e:
        print("HTTP Error Code:", e.code)
        print("HTTP Error Body:", e.read().decode())
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_cobalt()
