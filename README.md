# PitchCraft AI

Enter a one-sentence business idea and get a 5-section startup pitch deck from Gemini, downloadable as a .txt file.

## Run locally
```bash
pip install -r requirements.txt
mkdir -p .streamlit
echo 'GEMINI_API_KEY = "your-key-here"' > .streamlit/secrets.toml
streamlit run app.py
```

## Deploy
Streamlit Community Cloud: main file `app.py`, then add `GEMINI_API_KEY = "..."` under Settings -> Secrets.

## Usage stats (optional)
Add a long random value to Secrets: `STATS_KEY = "some-long-random-text"`.
Then open `https://YOUR-APP.streamlit.app/?stats=some-long-random-text` to see hits, misses, hit rate and near-repeat misses.
Counts live in memory and reset when the app restarts. Each request also writes one anonymous line to the app logs (event + a short random code, never the idea text).
