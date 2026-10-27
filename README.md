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
