import os
import random
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from ytmusicapi import YTMusic
import yt_dlp
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="Vibe Music API Server")

# Allow requests from all origins (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize YTMusic
try:
    yt = YTMusic()
except Exception as e:
    print("Warning: Failed to initialize YTMusic with default settings.", e)

# Helper to format YTMusic song data into our app's Song model
def format_song(track):
    video_id = track.get('videoId')
    if not video_id:
        return None
    
    # Get artist name
    artists = track.get('artists', [])
    artist_name = "Unknown Artist"
    if artists:
        if isinstance(artists, list):
            artist_name = artists[0].get('name', 'Unknown Artist')
        elif isinstance(artists, str):
            artist_name = artists
            
    # Get thumbnail
    thumbnails = track.get('thumbnails', []) or track.get('thumbnail', [])
    album_art = ""
    if thumbnails:
        album_art = thumbnails[-1].get('url', '') # Use highest resolution
        
    duration = track.get('duration', '3:00')
    
    return {
        "id": video_id,
        "title": track.get('title', 'Unknown Title'),
        "artist": artist_name,
        "albumArtUrl": album_art,
        "duration": duration,
        "isLiked": False
    }

@app.get("/api/search")
def search_all(q: str = Query(..., min_length=1)):
    try:
        # Fetch songs and artists in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_songs = executor.submit(yt.search, q, filter="songs", limit=50)
            future_artists = executor.submit(yt.search, q, filter="artists", limit=5)
            
            # Format songs
            song_results = future_songs.result()
            songs = []
            for track in song_results:
                formatted = format_song(track)
                if formatted:
                    songs.append(formatted)
            
            # Format artists
            artist_results = future_artists.result()
            artists = []
            for art in artist_results:
                thumbnails = art.get('thumbnails', [])
                img_url = thumbnails[-1].get('url', '') if thumbnails else ''
                artists.append({
                    "id": art.get('browseId', ''),
                    "name": art.get('title', 'Unknown Artist'),
                    "imageUrl": img_url
                })
                
        top_result = songs[0] if songs else None
        remaining_songs = songs[1:] if songs else []
        
        return {
            "topResult": top_result,
            "songs": remaining_songs,
            "artists": artists
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/api/suggestions")
def get_suggestions(q: str = Query(..., min_length=1)):
    try:
        suggestions = yt.get_search_suggestions(q)
        return {"suggestions": suggestions if suggestions else []}
    except Exception as e:
        return {"suggestions": []}

# Randomized query pools for each category to ensure fresh results on every refresh
QUERY_POOLS = {
    "trending": [
        "trending music hits 2025", "viral songs today", "top trending songs",
        "most popular songs right now", "trending hits playlist", "new trending music",
        "hit songs 2025", "best songs this week", "chart toppers today",
        "popular music worldwide", "global hits 2025", "latest trending songs",
        "super hit songs", "today top songs", "best songs this month"
    ],
    "hindi": [
        "Hindi top songs 2025", "latest Hindi songs", "Bollywood new songs",
        "Hindi romantic songs", "Hindi hits playlist", "new Bollywood hits",
        "best Hindi songs", "Hindi DJ songs", "Bollywood party songs",
        "Hindi sad songs latest", "Hindi love songs 2025", "Bollywood superhit",
        "latest Hindi album songs", "Hindi pop songs", "trending Hindi music"
    ],
    "english": [
        "English top songs 2025", "latest English songs", "English pop hits",
        "top English music playlist", "English romantic songs", "best English songs",
        "English party songs", "latest English pop", "top 50 English songs",
        "English viral songs", "English new releases", "Western pop hits",
        "English chart toppers", "best English pop 2025", "English love songs"
    ],
    "haryanvi": [
        "Haryanvi top songs", "latest Haryanvi songs", "Haryanvi DJ songs",
        "new Haryanvi hit songs", "Haryanvi dance songs", "best Haryanvi music",
        "Haryanvi superhit songs", "Haryanvi party songs", "trending Haryanvi",
        "Haryanvi new songs 2025", "Haryanvi love songs", "Haryanvi viral songs",
        "top Haryanvi hits", "Haryanvi remix songs", "Haryanvi popular songs"
    ],
    "bhojpuri": [
        "Bhojpuri top songs", "latest Bhojpuri songs", "Bhojpuri DJ songs",
        "new Bhojpuri hits", "Bhojpuri dance songs", "best Bhojpuri music",
        "Bhojpuri superhit songs", "trending Bhojpuri songs", "Bhojpuri party mix",
        "Bhojpuri new songs 2025", "Bhojpuri love songs", "Bhojpuri viral hits",
        "Bhojpuri romantic songs", "Bhojpuri popular songs", "Bhojpuri top hits"
    ],
    "rajasthani": [
        "Rajasthani top songs", "latest Rajasthani songs", "Rajasthani folk songs",
        "new Rajasthani music", "Rajasthani dance songs", "best Rajasthani songs",
        "Rajasthani superhit songs", "Marwadi songs", "trending Rajasthani music",
        "Rajasthani new songs 2025", "Rajasthani love songs", "Rajasthani DJ remix",
        "Rajasthani popular songs", "Marwadi hit songs", "Rajasthani folk hits"
    ],
    "punjabi": [
        "Punjabi top songs 2025", "latest Punjabi songs", "Punjabi hits playlist",
        "new Punjabi songs", "Punjabi DJ songs", "best Punjabi music",
        "Punjabi party songs", "trending Punjabi music", "Punjabi superhit songs",
        "Punjabi love songs 2025", "Punjabi viral songs", "Punjabi new releases"
    ]
}

@app.get("/api/home")
def get_home_data():
    try:
        # Pick a random query from each pool for fresh results every time
        categories = {}
        for lang, pool in QUERY_POOLS.items():
            if lang == "punjabi":
                continue  # Punjabi is handled separately if needed
            categories[lang] = random.choice(pool)
        
        # Also add punjabi
        categories["punjabi"] = random.choice(QUERY_POOLS["punjabi"])
        
        results = {}
        
        # Query YouTube Music in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=9) as executor:
            future_to_lang = {
                executor.submit(yt.search, query, filter="songs", limit=20): lang
                for lang, query in categories.items()
            }
            future_artists = executor.submit(yt.get_charts)
            
            for future in future_to_lang:
                lang = future_to_lang[future]
                try:
                    search_res = future.result()
                    songs = []
                    for track in search_res:
                        formatted = format_song(track)
                        if formatted:
                            songs.append(formatted)
                    # Shuffle results to get different ordering each time
                    random.shuffle(songs)
                    results[lang] = songs[:15]  # Return up to 15 songs per category
                except Exception as e:
                    print(f"Error fetching {lang}: {e}")
                    results[lang] = []
            
            # Fetch Top Artists
            top_artists = []
            try:
                charts = future_artists.result()
                artists_list = charts.get('artists', [])
                # Shuffle and pick random artists
                shuffled_artists = list(artists_list)
                random.shuffle(shuffled_artists)
                for artist in shuffled_artists[:10]:
                    thumbnails = artist.get('thumbnails', [])
                    img_url = thumbnails[-1].get('url', '') if thumbnails else ''
                    top_artists.append({
                        "id": artist.get('browseId', ''),
                        "name": artist.get('title', 'Unknown Artist'),
                        "imageUrl": img_url
                    })
            except Exception as chart_err:
                print("Failed to get charts artists:", chart_err)
                fallback_names = ["The Weeknd", "Dua Lipa", "Drake", "Taylor Swift", "Post Malone", "Arijit Singh", "AP Dhillon", "Diljit Dosanjh"]
                for i, name in enumerate(fallback_names):
                    top_artists.append({
                        "id": f"fallback_{i}",
                        "name": name,
                        "imageUrl": ""
                    })

        return {
            "trendingSongs": results.get("trending", []),
            "hindiHits": results.get("hindi", []),
            "englishHits": results.get("english", []),
            "haryanviHits": results.get("haryanvi", []),
            "bhojpuriHits": results.get("bhojpuri", []),
            "rajasthaniHits": results.get("rajasthani", []),
            "punjabiHits": results.get("punjabi", []),
            "topArtists": top_artists
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Home data fetch failed: {str(e)}")

@app.get("/api/radio")
def get_radio_songs(videoId: str = Query(..., min_length=1)):
    try:
        playlist = yt.get_watch_playlist(videoId=videoId, limit=30)
        tracks = playlist.get('tracks', [])
        songs = []
        for track in tracks:
            formatted = format_song(track)
            if formatted:
                songs.append(formatted)
        return songs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Radio failed: {str(e)}")

@app.get("/api/artist")
def get_artist_songs(artistId: str = Query(None), name: str = Query(...)):
    try:
        # If valid artistId, try fetching via get_artist
        if artistId and artistId.startswith("UC"):
            try:
                artist_data = yt.get_artist(artistId)
                songs_sec = artist_data.get('songs', {})
                playlist_id = songs_sec.get('browseId')
                
                # Fetch full playlist if browseId exists
                if playlist_id:
                    playlist = yt.get_playlist(playlist_id)
                    tracks = playlist.get('tracks', [])
                else:
                    tracks = songs_sec.get('results', [])
                
                songs = []
                for track in tracks:
                    formatted = format_song(track)
                    if formatted:
                        songs.append(formatted)
                if songs:
                    return songs
            except Exception as artist_err:
                print("Failed to get artist details, falling back to search:", artist_err)

        # Fallback: search songs by artist name
        results = yt.search(f"{name} songs", filter="songs", limit=50)
        songs = []
        for track in results:
            formatted = format_song(track)
            if formatted:
                songs.append(formatted)
        return songs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Artist fetch failed: {str(e)}")

def extract_stream_from_cobalt(video_id: str) -> str:
    instances = [
        "https://co.wuk.sh",
        "https://cobalt.moe",
        "https://cobalt.cr.us.to"
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
    
    import urllib.request, json, ssl
    context = ssl._create_unverified_context()
    
    for api_url in instances:
        try:
            req = urllib.request.Request(api_url, headers=headers, data=json.dumps(body).encode())
            res = urllib.request.urlopen(req, context=context, timeout=5).read().decode()
            data = json.loads(res)
            stream_url = data.get("url")
            if stream_url:
                print(f"Cobalt success: {api_url}")
                return stream_url
        except Exception as e:
            print(f"Cobalt failed on {api_url}: {e}")
            
    return None

@app.get("/api/stream")
def get_stream_url(videoId: str = Query(..., min_length=1)):
    # Try Cobalt API first (essential for datacenter/cloud hosting like Hugging Face or Render)
    try:
        cobalt_url = extract_stream_from_cobalt(videoId)
        if cobalt_url:
            return {"url": cobalt_url}
    except Exception as cobalt_err:
        print("Cobalt extraction failed, falling back to local ytdl:", cobalt_err)

    # Fallback to yt-dlp (works on local PC residential connections)
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'extract_flat': False,
    }
    
    try:
        url = f"https://www.youtube.com/watch?v={videoId}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise HTTPException(status_code=404, detail="Stream info not found")
            
            stream_url = info.get('url')
            if not stream_url:
                raise HTTPException(status_code=404, detail="Direct streaming URL not found")
                
            return {"url": stream_url}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("Traceback:", tb)
        raise HTTPException(status_code=500, detail=f"Stream url extraction failed: {str(e)} | Traceback: {tb}")

@app.get("/api/test_cobalt")
def test_cobalt_endpoint(videoId: str = "eXkHvT--DBU"):
    instances = [
        "https://co.wuk.sh",
        "https://cobalt.moe",
        "https://cobalt.cr.us.to"
    ]
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    body = {
        "url": f"https://www.youtube.com/watch?v={videoId}",
        "downloadMode": "audio"
    }
    
    import urllib.request, json, ssl
    context = ssl._create_unverified_context()
    
    results = {}
    for api_url in instances:
        try:
            req = urllib.request.Request(api_url, headers=headers, data=json.dumps(body).encode())
            res = urllib.request.urlopen(req, context=context, timeout=5).read().decode()
            data = json.loads(res)
            stream_url = data.get("url")
            results[api_url] = {"status": "success", "url": stream_url}
        except Exception as e:
            results[api_url] = {"status": "failed", "error": str(e)}
            
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
