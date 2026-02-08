# BPM Workout Playlist Generator

Generate a Spotify playlist that matches your workout intensity — songs ramp up from a chill warmup to peak energy, then bring you back down for a cool-off.

## BPM data powered by [GetSongBPM.com](https://getsongbpm.com)

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

You need:

-   **Spotify Developer App** — get credentials at https://developer.spotify.com/dashboard
    -   Set the Redirect URI to `http://localhost:8501`
-   **GetSongBPM API Key** — sign up at https://getsongbpm.com/api

### 3. Run the app

```bash
streamlit run app.py
```

## How It Works

1. Log in with your Spotify account
2. Select playlists you want to source songs from
3. Set your workout duration
4. The app fetches BPM data for each track, then builds a playlist following a trapezoidal BPM curve:
    - **Warmup** (25%) — low to mid BPM
    - **Peak** (50%) — highest BPM songs
    - **Cooldown** (25%) — mid to low BPM
5. Save the generated playlist directly to your Spotify account
