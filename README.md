# BPM Workout Playlist Generator

Generate a Spotify playlist that matches your workout intensity — songs ramp up from a chill warmup to peak energy, then bring you back down for a cool-off. Powered by a two-agent AI system for personalised workout coaching and intelligent music curation.

## Sponsors

-   **K2-Think v2 (MBZUAI-IFM)** — reasoning model for exercise science & workout design
-   **Dedalus Labs** — AI cloud platform for intelligent music curation & health insights

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
    -   Set the Redirect URI to `http://127.0.0.1:8501`
-   **K2 API Key** — for K2-Think v2 access at https://api.k2think.ai/
-   **Dedalus API Key** — from https://dedaluslabs.ai/

### 3. Download the BPM dataset

Download the Spotify tracks dataset from Hugging Face:

```bash
mkdir -p data
curl -L -o data/spotify_tracks.csv https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset/resolve/main/dataset.csv
```

### 4. Run the app

```bash
streamlit run app.py
```

## How It Works

1. Log in with your Spotify account
2. Fill in your runner profile (age, fitness level, goal, health notes)
3. Select playlists to source songs from — or skip and enter genre preferences
4. Set your workout duration
5. **Agent 1 (K2-Think)** designs a personalised workout with BPM targets, heart rate zones, and phase durations
6. **Agent 2 (Dedalus)** curates a playlist balancing your familiar tracks with new discoveries, ordered for smooth BPM transitions
7. View your BPM curve, tracklist with phase & source tags, and AI-generated health insights
8. Save the generated playlist directly to your Spotify account

## Architecture

```
Runner Profile + Duration
        │
        ▼
┌─────────────────────────┐
│  Agent 1: K2-Think      │  Workout plan with BPM targets
│  (K2-Think API)         │  HR zones, phase fractions
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Agent 2: Dedalus       │  Curated playlist
│  Music Curator          │  Familiar + Discovery tracks
└───────────┬─────────────┘
            │
            ▼
    Results + Health Insights
            │
            ▼
      Save to Spotify
```
