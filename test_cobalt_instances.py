import urllib.request
import json
import urllib.error
import ssl

ssl_context = ssl._create_unverified_context()

def get_cobalt_stream(video_id):
    instances = [
        "https://cobalt.cr.us.to",
        "https://cobalt.moe",
        "https://co.wuk.sh",
        "https://api.cobalt.tools"  # Backup
    ]
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    body = {
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "downloadMode": "audio"
    }
    
    for api_url in instances:
        print(f"Trying Cobalt instance: {api_url}...")
        try:
            req = urllib.request.Request(api_url, headers=headers, data=json.dumps(body).encode())
            # Short timeout of 5 seconds
            res_content = urllib.request.urlopen(req, context=ssl_context, timeout=5).read().decode()
            data = json.loads(res_content)
            
            stream_url = data.get("url")
            if stream_url:
                print(f"-> SUCCESS using {api_url}!")
                return stream_url
            else:
                print(f"No url returned from {api_url}. Response: {data}")
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code} on {api_url}: {e.read().decode()}")
        except Exception as err:
            print(f"Failed on {api_url}: {err}")
            
    return None

if __name__ == "__main__":
    vid = "eXkHvT--DBU"
    url = get_cobalt_stream(vid)
    if url:
        print("\nExtracted Stream URL:\n", url)
    else:
        print("\nFailed to extract stream URL from all instances.")
