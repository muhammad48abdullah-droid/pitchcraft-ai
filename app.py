import os
import streamlit as st
from google import genai

# -----------------------------------------------------------------------------
# 1. Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="PitchCraft AI - Startup Pitch Deck Generator",
    page_icon="🚀",
    layout="centered"
)

# -----------------------------------------------------------------------------
# 2. API Key Setup
# -----------------------------------------------------------------------------
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.error("⚠️ GEMINI_API_KEY not found! Please add it to Streamlit Secrets or environment variables.")
    st.stop()

# Initialize Google GenAI Client
client = genai.Client(api_key=api_key)

# -----------------------------------------------------------------------------
# 3. UI Layout & Input
# -----------------------------------------------------------------------------
st.title("🚀 PitchCraft AI")
st.write("Turn your rough one-sentence business idea into a professional 5-section startup pitch deck instantly using Google Gemini.")

idea = st.text_input(
    "Your business idea (one sentence)", 
    placeholder="e.g., bicycles on rent"
)

# -----------------------------------------------------------------------------
# 4. Generation & Gemini API Integration
# -----------------------------------------------------------------------------
if st.button("✨ Generate Pitch Deck", type="primary"):
    if not idea.strip():
        st.warning("⚠️ Please enter a business idea first!")
    else:
        with st.spinner("Crafting your professional pitch deck..."):
            try:
                prompt = f"""
                You are an expert startup venture capitalist and pitch deck consultant. 
                Based on the following rough business idea: "{idea}"
                
                Generate a professional 5-section startup pitch deck with clear headings:
                1. Problem Statement
                2. Unique Solution
                3. Target Market Analysis
                4. Monetization & Revenue Model
                5. Catchy Tagline & Marketing Slogan
                
                Keep the tone professional, structured, and compelling. Use markdown formatting.
                """
                
                # Using gemini-3.8-flash as recommended by the API
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt
                )
                
                # Save to session state so it persists on UI interactions
                st.session_state["pitch_text"] = response.text
                st.session_state["pitch_idea"] = idea
                
            except Exception as e:
                st.error(f"Generation failed: {str(e)}")

# -----------------------------------------------------------------------------
# 5. Display Results & Download Button
# -----------------------------------------------------------------------------
if "pitch_text" in st.session_state:
    st.markdown("---")
    st.subheader("📋 Your Generated Pitch Deck")
    st.markdown(st.session_state["pitch_text"])
    
    # Clean filename for download
    safe_filename = "".join(c if c.isalnum() else "_" for c in st.session_state["pitch_idea"][:25]).strip("_")
    
    st.download_button(
        label="📥 Download Pitch Deck as Text File",
        data=st.session_state["pitch_text"],
        file_name=f"pitch_deck_{safe_filename}.txt",
        mime="text/plain"
    )
