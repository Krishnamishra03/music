import express from 'express';
import cors from 'cors';
import { Innertube, Platform } from 'youtubei.js';

// Setup custom JavaScript interpreter shim for signature deciphering
Platform.shim.eval = async (code, env) => {
  let script = "";
  if (code.code) script += code.code + "\n";
  if (code.output) script += code.output;
  else script += code;
  return new Function(...Object.keys(env), script)(...Object.values(env));
};

const app = express();
const PORT = 8000;

app.use(cors({ origin: '*' }));
app.use(express.json());

let yt;
let startupError = null;

// Initialize YouTube.js
async function initYouTube() {
  try {
    console.log("Initializing Innertube...");
    yt = await Innertube.create();
    console.log("Innertube initialized successfully.");
    
    // Cache popular artists on startup
    await cacheTopArtists();
  } catch (err) {
    console.error("Failed to initialize Innertube:", err);
    startupError = {
      message: err.message,
      stack: err.stack,
      time: new Date().toISOString()
    };
  }
}

// Debug endpoint to check container status and errors
app.get('/api/debug', (req, res) => {
  res.json({
    status: startupError ? "error" : "ok",
    startupError,
    env: {
      nodeVersion: process.version,
      platform: process.platform,
      arch: process.arch
    }
  });
});

// Middleware to ensure Innertube is initialized
app.use((req, res, next) => {
  if (req.path === '/api/debug') return next();
  if (startupError) {
    return res.status(500).json({
      error: "Backend failed to initialize YouTube client.",
      details: startupError.message
    });
  }
  if (!yt) {
    return res.status(503).json({
      error: "Backend is still initializing YouTube client, please retry in a few seconds."
    });
  }
  next();
});

// Helper to format thumbnail URLs into high-res images
function getThumbnailUrl(item) {
  const contents = item.thumbnail?.contents || item.thumbnails || item.thumbnail;
  let url = "";
  if (Array.isArray(contents) && contents.length > 0) {
    url = contents[contents.length - 1]?.url || contents[contents.length - 1];
  } else if (typeof contents === 'string') {
    url = contents;
  } else if (contents && typeof contents === 'object' && contents.url) {
    url = contents.url;
  }
  
  if (url && typeof url === 'string') {
    // Enhance to high-res if it's a googleusercontent or lh3 thumbnail
    return url.replace(/=w\d+-h\d+/, '=w500-h500');
  }
  return url || "";
}

// Helper to extract artists list as a string
function extractArtists(item) {
  if (item.artists && Array.isArray(item.artists) && item.artists.length > 0) {
    return item.artists.map(a => a.name).join(' & ');
  }
  if (item.authors && Array.isArray(item.authors) && item.authors.length > 0) {
    return item.authors.map(a => a.name).join(' & ');
  }
  if (item.author) {
    return typeof item.author === 'string' ? item.author : (item.author.name || "");
  }
  if (item.flex_columns && item.flex_columns.length > 1) {
    const runs = item.flex_columns[1].title?.runs || item.flex_columns[1].text?.runs;
    if (runs && Array.isArray(runs)) {
      const artistNames = [];
      for (const run of runs) {
        if (run.text === ' • ') break;
        if (run.text !== ' & ' && run.text !== ', ') {
          artistNames.push(run.text);
        }
      }
      if (artistNames.length > 0) {
        return artistNames.join(' & ');
      }
    }
  }
  return "Unknown Artist";
}

// Helper to extract duration text
function extractDuration(item) {
  if (item.duration) {
    if (typeof item.duration === 'string') return item.duration;
    if (item.duration.text) return item.duration.text;
  }
  if (item.flex_columns && item.flex_columns.length > 1) {
    const runs = item.flex_columns[1].title?.runs || item.flex_columns[1].text?.runs;
    if (runs && Array.isArray(runs)) {
      const durRun = runs.find(r => /^\d+:\d+$/.test(r.text));
      if (durRun) return durRun.text;
    }
  }
  return "3:00";
}

// Format raw YouTube.js item into Song schema
function formatSong(item) {
  const id = item.id || item.videoId || item.endpoint?.payload?.videoId;
  if (!id) return null;
  
  const title = item.title?.toString() || item.name || (item.flex_columns?.[0]?.title?.toString() || item.flex_columns?.[0]?.text?.toString()) || "Unknown Title";
  const artist = extractArtists(item);
  const albumArtUrl = getThumbnailUrl(item);
  const duration = extractDuration(item);
  
  return {
    id,
    title,
    artist,
    albumArtUrl,
    duration,
    isLiked: false
  };
}

// Format raw YouTube.js item into Artist schema
function formatArtist(artist) {
  const id = artist.id || artist.channel_id || artist.endpoint?.payload?.browseId || "";
  const name = artist.name || artist.title?.toString() || "";
  const imageUrl = getThumbnailUrl(artist);
  return { id, name, imageUrl };
}

// In-memory cache for popular artists
let cachedTopArtists = [];
const POPULAR_ARTIST_NAMES = [
  "The Weeknd", "Dua Lipa", "Drake", "Taylor Swift", 
  "Post Malone", "Arijit Singh", "AP Dhillon", "Diljit Dosanjh"
];

async function cacheTopArtists() {
  console.log("Caching top artists...");
  try {
    const results = await Promise.all(POPULAR_ARTIST_NAMES.map(name => 
      yt.music.search(name, { type: 'artist' }).catch(err => {
        console.error(`Failed to search artist ${name}:`, err);
        return null;
      })
    ));
    
    cachedTopArtists = [];
    for (let i = 0; i < POPULAR_ARTIST_NAMES.length; i++) {
      const res = results[i];
      let artist = null;
      if (res && res.contents && res.contents.length > 0) {
        artist = formatArtist(res.contents[0]);
      }
      if (artist && artist.id) {
        cachedTopArtists.push(artist);
      } else {
        cachedTopArtists.push({
          id: `fallback_${i}`,
          name: POPULAR_ARTIST_NAMES[i],
          imageUrl: ""
        });
      }
    }
    console.log(`Cached ${cachedTopArtists.length} top artists.`);
  } catch (e) {
    console.error("Failed to cache top artists:", e);
    cachedTopArtists = POPULAR_ARTIST_NAMES.map((name, i) => ({
      id: `fallback_${i}`,
      name,
      imageUrl: ""
    }));
  }
}

// Helper to shuffle arrays
function shuffle(array) {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}

// Helper to pick random item from array
function pickRandom(array) {
  return array[Math.floor(Math.random() * array.length)];
}

// Random query pools from server.py
const QUERY_POOLS = {
  trending: [
    "trending music hits 2025", "viral songs today", "top trending songs",
    "most popular songs right now", "trending hits playlist", "new trending music",
    "hit songs 2025", "best songs this week", "chart toppers today",
    "popular music worldwide", "global hits 2025", "latest trending songs",
    "super hit songs", "today top songs", "best songs this month"
  ],
  hindi: [
    "Hindi top songs 2025", "latest Hindi songs", "Bollywood new songs",
    "Hindi romantic songs", "Hindi hits playlist", "new Bollywood hits",
    "best Hindi songs", "Hindi DJ songs", "Bollywood party songs",
    "Hindi sad songs latest", "Hindi love songs 2025", "Bollywood superhit",
    "latest Hindi album songs", "Hindi pop songs", "trending Hindi music"
  ],
  english: [
    "English top songs 2025", "latest English songs", "English pop hits",
    "top English music playlist", "English romantic songs", "best English songs",
    "English party songs", "latest English pop", "top 50 English songs",
    "English viral songs", "English new releases", "Western pop hits",
    "English chart toppers", "best English pop 2025", "English love songs"
  ],
  haryanvi: [
    "Haryanvi top songs", "latest Haryanvi songs", "Haryanvi DJ songs",
    "new Haryanvi hit songs", "Haryanvi dance songs", "best Haryanvi music",
    "Haryanvi superhit songs", "Haryanvi party songs", "trending Haryanvi",
    "Haryanvi new songs 2025", "Haryanvi love songs", "Haryanvi viral songs",
    "top Haryanvi hits", "Haryanvi remix songs", "Haryanvi popular songs"
  ],
  bhojpuri: [
    "Bhojpuri top songs", "latest Bhojpuri songs", "Bhojpuri DJ songs",
    "new Bhojpuri hits", "Bhojpuri dance songs", "best Bhojpuri music",
    "Bhojpuri superhit songs", "trending Bhojpuri songs", "Bhojpuri party mix",
    "Bhojpuri new songs 2025", "Bhojpuri love songs", "Bhojpuri viral hits",
    "Bhojpuri romantic songs", "Bhojpuri popular songs", "Bhojpuri top hits"
  ],
  rajasthani: [
    "Rajasthani top songs", "latest Rajasthani songs", "Rajasthani folk songs",
    "new Rajasthani music", "Rajasthani dance songs", "best Rajasthani songs",
    "Rajasthani superhit songs", "Marwadi songs", "trending Rajasthani music",
    "Rajasthani new songs 2025", "Rajasthani love songs", "Rajasthani DJ remix",
    "Rajasthani popular songs", "Marwadi hit songs", "Rajasthani folk hits"
  ],
  punjabi: [
    "Punjabi top songs 2025", "latest Punjabi songs", "Punjabi hits playlist",
    "new Punjabi songs", "Punjabi DJ songs", "best Punjabi music",
    "Punjabi party songs", "trending Punjabi music", "Punjabi superhit songs",
    "Punjabi love songs 2025", "Punjabi viral songs", "Punjabi new releases"
  ]
};

// 1. Search endpoint
app.get('/api/search', async (req, res) => {
  const query = req.query.q;
  if (!query) {
    return res.status(400).json({ error: "Query parameter 'q' is required." });
  }

  try {
    const [songResults, artistResults] = await Promise.all([
      yt.music.search(query, { type: 'song' }).catch(() => null),
      yt.music.search(query, { type: 'artist' }).catch(() => null)
    ]);

    const songs = [];
    if (songResults && songResults.contents) {
      for (const section of songResults.contents) {
        if (section.contents) {
          for (const item of section.contents) {
            const formatted = formatSong(item);
            if (formatted) songs.push(formatted);
          }
        }
      }
    }

    const artists = [];
    if (artistResults && artistResults.contents) {
      for (const section of artistResults.contents) {
        if (section.contents) {
          for (const item of section.contents) {
            const formatted = formatArtist(item);
            if (formatted) artists.push(formatted);
          }
        }
      }
    }

    const topResult = songs.length > 0 ? songs[0] : null;
    const remainingSongs = songs.length > 1 ? songs.slice(1) : [];

    res.json({
      topResult,
      songs: remainingSongs,
      artists: artists.slice(0, 5)
    });
  } catch (err) {
    console.error("Search failed:", err);
    res.status(500).json({ error: `Search failed: ${err.message}` });
  }
});

// 2. Suggestions endpoint
app.get('/api/suggestions', async (req, res) => {
  const query = req.query.q;
  if (!query) {
    return res.json({ suggestions: [] });
  }

  try {
    const results = await yt.music.getSearchSuggestions(query);
    const suggestionsList = [];
    
    for (const section of results) {
      if (section.contents) {
        for (const item of section.contents) {
          if (item.type === 'SearchSuggestion') {
            const text = item.text?.toString();
            if (text) suggestionsList.push(text);
          }
        }
      }
    }
    
    res.json({ suggestions: suggestionsList });
  } catch (err) {
    console.error("Suggestions failed:", err);
    res.json({ suggestions: [] });
  }
});

// 3. Home endpoint
app.get('/api/home', async (req, res) => {
  try {
    const categories = {};
    for (const [lang, pool] of Object.entries(QUERY_POOLS)) {
      categories[lang] = pickRandom(pool);
    }

    const searchPromises = Object.entries(categories).map(([lang, query]) => 
      yt.music.search(query, { type: 'song' })
        .then(res => {
          const songs = [];
          if (res && res.contents) {
            for (const section of res.contents) {
              if (section.contents) {
                for (const item of section.contents) {
                  const formatted = formatSong(item);
                  if (formatted) songs.push(formatted);
                }
              }
            }
          }
          const shuffled = shuffle(songs);
          return { lang, songs: shuffled.slice(0, 15) };
        })
        .catch(err => {
          console.error(`Failed to fetch home for ${lang}:`, err);
          return { lang, songs: [] };
        })
    );

    const results = await Promise.all(searchPromises);
    const responseData = {
      trendingSongs: [],
      hindiHits: [],
      englishHits: [],
      haryanviHits: [],
      bhojpuriHits: [],
      rajasthaniHits: [],
      punjabiHits: [],
      topArtists: cachedTopArtists
    };

    for (const { lang, songs } of results) {
      if (lang === 'trending') responseData.trendingSongs = songs;
      else if (lang === 'hindi') responseData.hindiHits = songs;
      else if (lang === 'english') responseData.englishHits = songs;
      else if (lang === 'haryanvi') responseData.haryanviHits = songs;
      else if (lang === 'bhojpuri') responseData.bhojpuriHits = songs;
      else if (lang === 'rajasthani') responseData.rajasthaniHits = songs;
      else if (lang === 'punjabi') responseData.punjabiHits = songs;
    }

    res.json(responseData);
  } catch (err) {
    console.error("Home feed failed:", err);
    res.status(500).json({ error: `Home data fetch failed: ${err.message}` });
  }
});

// 4. Radio/Related tracks endpoint
app.get('/api/radio', async (req, res) => {
  const videoId = req.query.videoId;
  if (!videoId) {
    return res.status(400).json({ error: "videoId is required." });
  }

  try {
    const related = await yt.music.getRelated(videoId);
    const songs = [];
    
    if (related && related.contents) {
      for (const section of related.contents) {
        if (section.contents) {
          for (const item of section.contents) {
            if (item.item_type === 'song' || item.type === 'MusicResponsiveListItem') {
              const formatted = formatSong(item);
              if (formatted) songs.push(formatted);
            }
          }
        }
      }
    }
    
    res.json(songs);
  } catch (err) {
    console.error("Radio failed:", err);
    res.status(500).json({ error: `Radio failed: ${err.message}` });
  }
});

// 5. Artist detail endpoint
app.get('/api/artist', async (req, res) => {
  const artistId = req.query.artistId;
  const name = req.query.name;

  if (!name) {
    return res.status(400).json({ error: "Artist name is required." });
  }

  const fallbackToSearch = async () => {
    try {
      const searchRes = await yt.music.search(`${name} songs`, { type: 'song' });
      const songs = [];
      if (searchRes && searchRes.contents) {
        for (const section of searchRes.contents) {
          if (section.contents) {
            for (const item of section.contents) {
              const formatted = formatSong(item);
              if (formatted) songs.push(formatted);
            }
          }
        }
      }
      return songs;
    } catch (e) {
      console.error(`Fallback search for ${name} failed:`, e);
      return [];
    }
  };

  if (artistId && artistId.startsWith('UC')) {
    try {
      const artist = await yt.music.getArtist(artistId);
      const songSection = artist.sections?.find(s => s.type === 'MusicShelf' && s.title?.toString().toLowerCase().includes('songs'));
      
      if (songSection) {
        const playlistId = songSection.endpoint?.payload?.browseId;
        if (playlistId) {
          const cleanId = playlistId.startsWith('VL') ? playlistId.substring(2) : playlistId;
          const playlist = await yt.music.getPlaylist(cleanId);
          const tracks = playlist.contents || playlist.tracks;
          
          if (tracks && tracks.length > 0) {
            const songs = [];
            for (const track of tracks) {
              const formatted = formatSong(track);
              if (formatted) songs.push(formatted);
            }
            return res.json(songs);
          }
        }
        
        // If playlist fetching didn't return songs, use section contents
        if (songSection.contents && songSection.contents.length > 0) {
          const songs = [];
          for (const item of songSection.contents) {
            const formatted = formatSong(item);
            if (formatted) songs.push(formatted);
          }
          return res.json(songs);
        }
      }
      
      // Fallback if no song section found in artist details
      const songs = await fallbackToSearch();
      res.json(songs);
    } catch (err) {
      console.warn("Failed to get artist details, falling back to search:", err);
      const songs = await fallbackToSearch();
      res.json(songs);
    }
  } else {
    // If invalid ID or no ID, perform search immediately
    const songs = await fallbackToSearch();
    res.json(songs);
  }
});

// 6. Direct streaming URL endpoint with signature deciphering
app.get('/api/stream', async (req, res) => {
  const videoId = req.query.videoId;
  if (!videoId) {
    return res.status(400).json({ error: "videoId is required." });
  }

  try {
    const info = await yt.music.getInfo(videoId);
    const format = info.chooseFormat({ type: 'audio', quality: 'best' });
    
    if (!format) {
      return res.status(404).json({ error: "No suitable audio format found." });
    }

    const streamUrl = format.decipher ? await format.decipher(yt.session.player) : format.url;
    
    if (!streamUrl) {
      return res.status(500).json({ error: "Failed to decipher streaming URL." });
    }

    res.json({ url: streamUrl });
  } catch (err) {
    console.error("Decipher streaming URL failed:", err);
    res.status(500).json({ error: `Stream url extraction failed: ${err.message}` });
  }
});

// Start Express App
initYouTube().then(() => {
  app.listen(PORT, () => {
    console.log(`=============================================`);
    console.log(`Vibe Music Node Server listening on port ${PORT}`);
    console.log(`=============================================`);
  });
});
