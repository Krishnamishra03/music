import urllib.request
import json
import ssl

ssl_context = ssl._create_unverified_context()

def get_piped_stream(video_id):
    instances = [
        "https://pipedapi.lunar.icu",
        "https://pipedapi.adminforge.de",
        "https://piped-api.garudalinux.org",
        "https://pipedapi.ox.xyz",
        "https://pipedapi.smn.dev",
        "https://pipedapi.kavin.rocks"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for api_url in instances:
        stream_url = f"{api_url}/streams/{video_id}"
        print(f"Trying Piped instance: {api_url}...")
        try:
            req = urllib.request.Request(stream_url, headers=headers)
            res_content = urllib.request.urlopen(req, context=ssl_context, timeout=5).read().decode()
            data = json.loads(res_content)
            
            audio_streams = data.get("audioStreams", [])
            if audio_streams:
                # Get the first audio stream
                best_audio = audio_streams[0]
                audio_url = best_audio.get("url")
                if audio_url:
                    print(f"-> SUCCESS using {api_url}!")
                    return audio_url
            else:
                print(f"No audio streams found on {api_url}")
        except Exception as err:
            print(f"Failed on {api_url}: {err}")
            
    return None

if __name__ == "__main__":
    vid = "eXkHvT--DBU"
    url = get_piped_stream(vid)
    if url:
        print("\nExtracted Stream URL:\n", url)
    else:
        print("\nFailed to extract stream URL from all instances.")
