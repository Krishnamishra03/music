import os
import sys

def setup():
    print("==================================================================")
    print("         Svara Backend - YouTube Music Authentication Setup       ")
    print("==================================================================")
    print("\nTo bypass YouTube blocking on Render/Hugging Face, we need to extract")
    print("your YouTube Music request headers from your browser.")
    print("\nSteps:")
    print("1. Open Chrome/Firefox and go to: https://music.youtube.com")
    print("2. Make sure you are logged in to your Google Account.")
    print("3. Press F12 (Inspect Element) and navigate to the 'Network' tab.")
    print("4. Search for a request named 'browse' or 'search' (under Fetch/XHR).")
    print("5. Right-click on that request -> Copy -> Copy request headers.")
    print("\nOnce copied, paste the raw headers here (Press Enter twice when done):")
    print("------------------------------------------------------------------")
    
    lines = []
    while True:
        try:
            line = input()
            if not line and (len(lines) == 0 or lines[-1] == ""):
                break
            lines.append(line)
        except EOFError:
            break
            
    raw_headers = "\n".join(lines).strip()
    
    if not raw_headers:
        print("Error: No headers pasted. Setup aborted.")
        return

    try:
        import ytmusicapi
    except ImportError:
        print("Installing ytmusicapi library...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ytmusicapi"])
        import ytmusicapi

    try:
        # Save to headers_auth.json
        ytmusicapi.setup(filepath="headers_auth.json", headers_raw=raw_headers)
        print("\n[SUCCESS] headers_auth.json has been created successfully!")
        print("You can now push this file along with your server to Render.")
    except Exception as e:
        print(f"\n[ERROR] Failed to save headers: {e}")

if __name__ == "__main__":
    setup()
