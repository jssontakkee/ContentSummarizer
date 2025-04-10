import streamlit as st
import validators
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import UnstructuredURLLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
# Corrected import for youtube-transcript-api exceptions
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptAvailable
import re
import urllib3
import time
import random

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- IMPORTANT ---
# Replace with your actual Groq API key before deployment if needed
# Keep the placeholder if you intend for users to enter it, but the code currently uses this variable directly.
GROQ_API_KEY = "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"  # Replace this with your actual API key

# Define function to extract YouTube ID from URL
def extract_youtube_id(url):
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)',
        r'(?:youtube\.com\/embed\/)([\w-]+)',
        r'(?:youtube\.com\/v\/)([\w-]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# Function to get YouTube transcript with improved error handling and corrected exceptions
def get_youtube_transcript(video_id):
    try:
        # Get the list of available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # First try to get English transcript
        try:
            transcript = transcript_list.find_transcript(['en'])
            st.markdown("""
            <div class="success-message">
                <span>✅ Found English transcript!</span>
            </div>
            """, unsafe_allow_html=True)
            fetched = transcript.fetch()
            return " ".join([t['text'] for t in fetched])
        except NoTranscriptAvailable:
            # If English not available, try Hindi
            try:
                st.markdown("""
                <div class="info-message">
                    <span>ℹ️ English transcript not available. Trying Hindi...</span>
                </div>
                """, unsafe_allow_html=True)
                transcript = transcript_list.find_transcript(['hi'])
                st.markdown("""
                <div class="success-message">
                    <span>✅ Found Hindi transcript!</span>
                </div>
                """, unsafe_allow_html=True)

                # Translate to English
                st.markdown("""
                <div class="info-message">
                    <span>⏳ Translating Hindi transcript to English...</span>
                </div>
                """, unsafe_allow_html=True)
                translated_transcript = transcript.translate('en').fetch()
                st.markdown("""
                <div class="success-message">
                    <span>✅ Translation complete!</span>
                </div>
                """, unsafe_allow_html=True)
                return " ".join([t['text'] for t in translated_transcript])
            except NoTranscriptAvailable:
                # If neither English nor Hindi available, try any available language
                st.markdown("""
                <div class="info-message">
                    <span>ℹ️ Hindi transcript not available. Trying other languages...</span>
                </div>
                """, unsafe_allow_html=True)
                available_languages = [t.language for t in transcript_list]
                st.markdown(f"""
                <div class="info-message">
                    <span>ℹ️ Available languages: {', '.join(available_languages)}</span>
                </div>
                """, unsafe_allow_html=True)

                try:
                    # Iterate through available transcripts
                    for available_transcript in transcript_list:
                        lang = available_transcript.language
                        lang_code = available_transcript.language_code
                        st.markdown(f"""
                        <div class="info-message">
                            <span>ℹ️ Found {lang} ({lang_code}) transcript. Processing...</span>
                        </div>
                        """, unsafe_allow_html=True)
                        try:
                            # Translate to English if not already English
                            if lang_code != 'en':
                                st.markdown(f"""
                                <div class="info-message">
                                    <span>⏳ Translating {lang} transcript to English...</span>
                                </div>
                                """, unsafe_allow_html=True)
                                translated = available_transcript.translate('en').fetch()
                                st.markdown("""
                                <div class="success-message">
                                    <span>✅ Translation complete!</span>
                                </div>
                                """, unsafe_allow_html=True)
                                return " ".join([t['text'] for t in translated])
                            else:
                                fetched = available_transcript.fetch()
                                return " ".join([t['text'] for t in fetched])
                        except Exception as lang_error:
                            st.markdown(f"""
                            <div class="error-message">
                                <span>⚠️ Error processing {lang} transcript: {str(lang_error)}. Trying next...</span>
                            </div>
                            """, unsafe_allow_html=True)
                            continue # Try the next available language

                    # If loop finishes without returning, no usable transcript found
                    st.markdown("""
                    <div class="error-message">
                        <span>❌ No usable transcripts found after trying all available languages.</span>
                    </div>
                    """, unsafe_allow_html=True)
                    return None

                except Exception as e:
                    st.markdown(f"""
                    <div class="error-message">
                        <span>❌ Error iterating through available transcripts: {str(e)}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    return None

    except TranscriptsDisabled:
        st.markdown("""
        <div class="error-message">
            <span>❌ Transcripts are disabled for this video.</span>
        </div>
        """, unsafe_allow_html=True)
        return None
    except NoTranscriptAvailable:
         # This case might be hit if list_transcripts works but find_transcript fails unexpectedly later
         st.markdown("""
            <div class="error-message">
                <span>❌ No transcript was found for this video, even after checking available languages.</span>
            </div>
            """, unsafe_allow_html=True)
         return None
    except Exception as e:
        # Catch-all for other potential errors (network issues, API errors)
        st.markdown(f"""
        <div class="error-message">
            <span>❌ An unexpected error occurred while fetching transcripts: {str(e)}</span>
        </div>
        """, unsafe_allow_html=True)
        # Optionally try to list languages from the error if it follows the known pattern
        if "For this video" in str(e):
             error_msg = str(e)
             available_langs = re.findall(r'\* ([a-z\-]+) \("([^"]+)"\)', error_msg)
             if available_langs:
                 lang_codes = [code for code, name in available_langs]
                 st.markdown(f"""
                 <div class="info-message">
                    <span>ℹ️ Detected available language codes in error: {', '.join(lang_codes)}</span>
                 </div>
                 """, unsafe_allow_html=True)
        return None


# Custom CSS to make the UI more modern with glassmorphic effect
st.set_page_config(
    page_title="Content Summarizer Pro",
    page_icon="📚",
    layout="wide",
)

# Custom CSS for modern styling with glassmorphic effect
st.markdown("""
<style>
    /* Main background with gradient */
    .main {
        background: linear-gradient(135deg, #8A2BE2, #FF69B4, #9370DB, #6A5ACD, #BA55D3);
        background-size: 300% 300%;
        animation: gradient 15s ease infinite;
    }

    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* Floating gradient orbs in the background */
    .stApp::before {
        content: "";
        position: fixed;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle, rgba(255,105,180,0.8) 0%, rgba(255,105,180,0) 70%);
        top: -100px;
        left: 30%;
        border-radius: 50%;
        z-index: -1;
        animation: float 12s ease-in-out infinite;
    }

    .stApp::after {
        content: "";
        position: fixed;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(138,43,226,0.8) 0%, rgba(138,43,226,0) 70%);
        bottom: -150px;
        right: 20%;
        border-radius: 50%;
        z-index: -1;
        animation: float 15s ease-in-out infinite reverse;
    }

    @keyframes float {
        0% { transform: translate(0, 0); }
        50% { transform: translate(30px, 20px); }
        100% { transform: translate(0, 0); }
    }

    /* Additional orb */
    .stApp .block-container::before {
        content: "";
        position: fixed;
        width: 250px;
        height: 250px;
        background: radial-gradient(circle, rgba(106,90,205,0.8) 0%, rgba(106,90,205,0) 70%);
        top: 60%;
        left: 10%;
        border-radius: 50%;
        z-index: -1;
        animation: float 10s ease-in-out infinite 1s;
    }

    /* Glassmorphic effect for containers */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        background-color: rgba(255, 255, 255, 0.15);
        border-radius: 16px;
        margin: 15px;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        border-radius: 10px;
        padding: 10px 16px;
        background-color: rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(5px);
        margin-bottom: 10px;
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.18);
    }

    .stTabs [aria-selected="true"] {
        background-color: rgba(76, 175, 80, 0.7) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
    }

    div.stButton > button:first-child {
        background: linear-gradient(135deg, rgba(76, 175, 80, 0.9), rgba(46, 125, 50, 0.9));
        color: white;
        font-weight: bold;
        height: 3em;
        width: 100%;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.18);
        margin-top: 15px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(5px);
        transition: all 0.3s ease;
    }

    div.stButton > button:hover {
        background: linear-gradient(135deg, rgba(69, 160, 73, 0.9), rgba(46, 125, 50, 0.9));
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(0, 0, 0, 0.3);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }

    .url-input {
        border-radius: 10px;
        backdrop-filter: blur(5px);
        background-color: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.18);
    }

    .success-message {
        background-color: rgba(223, 240, 216, 0.7);
        border-left: 5px solid #4CAF50;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        backdrop-filter: blur(5px);
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
        color: #155724; /* Ensure text inside is readable */
    }

    .error-message {
        background-color: rgba(248, 215, 218, 0.7);
        border-left: 5px solid #dc3545;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        backdrop-filter: blur(5px);
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
        color: #721c24; /* Ensure text inside is readable */
    }

    .info-message {
        background-color: rgba(209, 236, 241, 0.7);
        border-left: 5px solid #17a2b8;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        backdrop-filter: blur(5px);
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
        color: #0c5460; /* Ensure text inside is readable */
    }

    .summary-container {
        background-color: rgba(249, 249, 249, 0.6);
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.18);
        margin-top: 20px;
        color: black; /* Make summary text black */
    }
    .summary-container p, .summary-container li {
        color: black; /* Ensure paragraph/list text is black */
    }
    .summary-container h3 {
        color: black; /* Make subheader black */
    }
    .summary-container hr {
        border-top: 1px solid rgba(0, 0, 0, 0.2);
    }
    .summary-container p[style*="text-align: right"] {
        color: #555 !important; /* Make metadata text darker grey */
    }

    .card {
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        backdrop-filter: blur(8px);
        background-color: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.18);
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
    }

    .metric-card {
        background-color: rgba(248, 249, 250, 0.25);
        border-radius: 16px;
        padding: 15px;
        text-align: center;
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.18);
        box-shadow: 0 4px 10px rgba(31, 38, 135, 0.2);
    }

    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #4CAF50;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .metric-label {
        font-size: 14px;
        color: #ffffff;
    }

    .highlight {
        background-color: rgba(248, 249, 250, 0.3);
        padding: 2px 5px;
        border-radius: 4px;
        font-family: monospace;
        backdrop-filter: blur(4px);
    }

    .stExpander {
        border-radius: 16px;
        box-shadow: 0 4px 10px rgba(31, 38, 135, 0.2);
        background-color: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.18);
        backdrop-filter: blur(5px);
    }
    /* Expander header text color */
    .stExpander > details > summary {
        color: white !important;
    }

    .progress-bar {
        width: 100%;
        background-color: rgba(243, 243, 243, 0.3);
        border-radius: 10px;
        margin-bottom: 10px;
        backdrop-filter: blur(4px);
        border: 1px solid rgba(255, 255, 255, 0.18);
    }

    .progress {
        height: 10px;
        background: linear-gradient(to right, #4CAF50, #2E7D32);
        border-radius: 10px;
        transition: width 0.5s ease-in-out;
    }

    .app-header {
        text-align: center;
        margin-bottom: 2rem;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
    }

    .app-title {
        font-size: 3rem;
        font-weight: bold;
        color: #ffffff;
        margin-bottom: 0.5rem;
    }

    .app-subtitle {
        font-size: 1.3rem;
        color: rgba(255, 255, 255, 0.9);
        margin-bottom: 1.5rem;
    }

    .url-container {
        backdrop-filter: blur(8px);
        background-color: rgba(255, 255, 255, 0.15);
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        border: 1px solid rgba(255, 255, 255, 0.18);
        margin-bottom: 20px;
    }

    .content-preview {
        max-height: 300px;
        overflow-y: auto;
        font-family: monospace;
        background-color: rgba(248, 249, 250, 0.2);
        padding: 15px;
        border-radius: 10px;
        border-left: 3px solid #4CAF50;
        margin-top: 10px;
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255, 255, 255, 0.18);
        color: white; /* Ensure preview text is readable */
    }

    .text-with-icon {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    /* Ensure icon text is readable */
    .text-with-icon span {
         color: inherit;
    }

    .youtube-video {
        border-radius: 16px;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        width: 100%;
        margin-top: 10px;
        border: 1px solid rgba(255, 255, 255, 0.18);
        aspect-ratio: 16 / 9; /* Maintain aspect ratio */
    }

    /* Custom styling for input fields */
    .stTextInput > div > div > input {
        background-color: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.18);
        color: black !important; /* Text color to black */
        border-radius: 10px;
        padding: 15px;
        backdrop-filter: blur(5px);
    }

    .stTextInput > div > div > input::placeholder {
        color: rgba(0, 0, 0, 0.5); /* Darker placeholder */
    }

    /* Custom styling for select boxes */
    .stSelectbox > div > div > div {
        background-color: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.18);
        color: black !important; /* Text color to black */
        border-radius: 10px;
        backdrop-filter: blur(5px);
    }
    /* Style for dropdown arrow */
    .stSelectbox svg {
        fill: black !important; /* Arrow color to black */
    }
    /* Style for dropdown options */
    div[data-baseweb="popover"] ul li {
         color: black !important;
         background-color: rgba(255, 255, 255, 0.9) !important;
    }
    div[data-baseweb="popover"] ul li:hover {
         background-color: rgba(200, 200, 200, 0.9) !important;
    }


    /* Custom styling for slider */
    .stSlider > div > div > div > div {
        background-color: rgba(76, 175, 80, 0.7);
    }

    .stSlider > div > div > div > div > div {
        color: white;
        background-color: #4CAF50;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
    }
    /* Slider labels */
    .stSlider label {
        color: white; /* Keep slider label white */
    }

    /* Typography for better readability on gradient background */
    p, span, h1, h2, h3, h4, li, label {
        color: white; /* Default text color */
    }

    h1, h2, h3, h4 {
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }

    /* Specific overrides for readability */
    div[data-testid="stForm"] label, /* Form labels */
    div[data-testid="stMarkdownContainer"] p, /* General markdown text */
    div[data-testid="stMarkdownContainer"] li, /* General markdown lists */
    .card ul li, /* Tips list */
    .card h4, /* Tips header */
    label[data-testid="stWidgetLabel"] p /* Widget labels like slider, selectbox */
    {
        color: white; /* Ensure these remain white */
    }

    /* Exception: Ensure message box text is readable based on its background */
    .success-message span, .success-message b { color: #155724; }
    .error-message span, .error-message b { color: #721c24; }
    .info-message span, .info-message b { color: #0c5460; }

</style>
""", unsafe_allow_html=True)

# App header with modern design
st.markdown("""
<div class="app-header">
    <div class="app-title">✨ Content Summarizer </div>
    <div class="app-subtitle">Instantly summarize YouTube videos and website content</div>
</div>
""", unsafe_allow_html=True)

# Create a two-column layout for the main content
col1, col2 = st.columns([3, 1])

with col2:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    # Model selection
    model_name = st.selectbox(
        "Model",
        ["gemma-7b-it", "llama3-8b-8192", "mixtral-8x7b-32768"],
        index=0,
        help="Select the AI model for summarization"
    )

    # Summary method
    chain_type = st.selectbox(
        "Summarization Method",
        ["map_reduce", "stuff", "refine"],
        index=0,
        help="Different methods balance speed vs. comprehensiveness"
    )

    # Summary length slider
    max_tokens = st.slider(
        "Summary Length (Max Tokens)",
        min_value=300,
        max_value=1200,
        value=600,
        step=100,
        help="Adjust the maximum detail level in your summary"
    )

    # Display info about the summary length
    if max_tokens <= 400:
        summary_type = "Concise"
        detail_level = "Brief overview with key points only"
    elif max_tokens <= 800:
        summary_type = "Balanced"
        detail_level = "Moderate detail covering main concepts"
    else:
        summary_type = "Detailed"
        detail_level = "In-depth coverage with extensive detail"

    # Use info message styling for summary type description, ensure text is readable
    st.markdown(f"""
    <div class="info-message" style="background-color: rgba(209, 236, 241, 0.4);">
        <b style="color: white;">{summary_type} Summary</b><br>
        <span style="color: white; opacity: 0.9;">{detail_level}</span>
    </div>
    """, unsafe_allow_html=True)

    # Display API status
    # Basic check if the key looks like a Groq key (starts with gsk_)
    # Avoid displaying the key itself
    is_api_key_present = GROQ_API_KEY and GROQ_API_KEY != "YOUR_GROQ_API_KEY_HERE" # Check if it's not empty or the placeholder
    is_api_key_plausible = is_api_key_present and GROQ_API_KEY.startswith("gsk_")

    if not is_api_key_present:
        st.markdown("""
        <div class="error-message" style="background-color: rgba(248, 215, 218, 0.4);">
            <span style="font-weight: bold; color: white;">⚠️ API Key Missing</span><br>
            <span style="color: white; opacity: 0.9;">Update the GROQ_API_KEY variable</span>
        </div>
        """, unsafe_allow_html=True)
    elif not is_api_key_plausible:
         st.markdown("""
        <div class="error-message" style="background-color: rgba(248, 215, 218, 0.4);">
            <span style="font-weight: bold; color: white;">⚠️ API Key Invalid Format</span><br>
            <span style="color: white; opacity: 0.9;">Groq API keys usually start with 'gsk_'</span>
        </div>
        """, unsafe_allow_html=True)
    else: # Key is present and looks plausible
        st.markdown("""
        <div class="success-message" style="background-color: rgba(223, 240, 216, 0.4);">
            <span style="font-weight: bold; color: white;">✅ API Ready</span><br>
            <span style="color: white; opacity: 0.9;">Groq API key is configured</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # Add tips in a card
    st.markdown("""
    <div class="card">
        <h4>💡 Tips</h4>
        <ul>
            <li><b>YouTube videos:</b> Works with any public video that has captions</li>
            <li><b>Websites:</b> Best results with news articles, blog posts and documentation</li>
            <li><b>Map-reduce:</b> Best for longer content with multiple sections</li>
            <li><b>Stuff method:</b> Fastest for shorter content (check context limits)</li>
            <li><b>Refine method:</b> Good balance for accuracy on longer texts</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

with col1:
    # URL input with better styling
    st.markdown('<div class="url-container">', unsafe_allow_html=True)
    url_placeholder = "Enter YouTube URL or website URL..."
    url = st.text_input("", placeholder=url_placeholder, label_visibility="collapsed")

    # Input validation with visual feedback
    if url:
        if validators.url(url):
            is_youtube = "youtube" in url or "youtu.be" in url
            if is_youtube:
                icon = "🎬"
                url_type = "YouTube Video"

                # Extract and display YouTube video ID
                video_id = extract_youtube_id(url)
                if video_id:
                    st.markdown(f"""
                    <div class="success-message">
                        <div class="text-with-icon">
                            <span>{icon} Valid {url_type} URL detected</span>
                        </div>
                    </div>
                    <iframe class="youtube-video" width="100%" height="450" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
                    """, unsafe_allow_html=True)
                else:
                     st.markdown("""
                    <div class="error-message">
                        <span>⚠️ Could not extract YouTube video ID from URL</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                icon = "🌐"
                url_type = "Website"
                st.markdown(f"""
                <div class="success-message">
                    <div class="text-with-icon">
                        <span>{icon} Valid {url_type} URL detected</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="error-message">
                <span>⚠️ Invalid URL format</span>
            </div>
            """, unsafe_allow_html=True)

    # Summarize button
    summarize_button = st.button("Summarize Content ✨", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Define summarization prompts dynamically based on slider
    # Note: Prompt engineering can significantly impact quality. These are basic examples.
    if max_tokens <= 400:
        map_template = "Briefly summarize the key points of this section:\n\n{text}\n\nCONCISE SUMMARY:"
        combine_template = "Combine these brief summaries into a single, concise overall summary of 2-3 sentences:\n\n{text}\n\nFINAL CONCISE SUMMARY:"
    elif max_tokens <= 800:
        map_template = "Summarize the main ideas and supporting details of this content:\n\n{text}\n\nBALANCED SUMMARY:"
        combine_template = "Create a comprehensive summary covering the main topics from these sections:\n\n{text}\n\nFINAL BALANCED SUMMARY:"
    else:
        map_template = "Provide a detailed summary of this content, including specific examples or arguments:\n\n{text}\n\nDETAILED SUMMARY:"
        combine_template = "Synthesize these detailed summaries into a thorough and in-depth final summary:\n\n{text}\n\nFINAL DETAILED SUMMARY:"

    map_prompt = PromptTemplate(template=map_template, input_variables=["text"])
    combine_prompt = PromptTemplate(template=combine_template, input_variables=["text"])


    # Main button action
    if summarize_button:
        # Re-check API key status before proceeding
        is_api_key_present = GROQ_API_KEY and GROQ_API_KEY != "YOUR_GROQ_API_KEY_HERE"
        is_api_key_plausible = is_api_key_present and GROQ_API_KEY.startswith("gsk_")

        if not is_api_key_present:
            st.markdown("""
            <div class="error-message">
                <span>⚠️ Please update the GROQ_API_KEY variable in the code with your actual API key</span>
            </div>
            """, unsafe_allow_html=True)
        elif not is_api_key_plausible:
            st.markdown("""
            <div class="error-message">
                <span>⚠️ API Key appears invalid. Please check the GROQ_API_KEY variable.</span>
            </div>
            """, unsafe_allow_html=True)
        elif not url:
            st.markdown("""
            <div class="error-message">
                <span>⚠️ Please enter a URL to summarize</span>
            </div>
            """, unsafe_allow_html=True)
        elif not validators.url(url):
            st.markdown("""
            <div class="error-message">
                <span>⚠️ Invalid URL format</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Create a container for the progress and results
            result_area = st.container()

            with result_area:
                st.markdown("""
                <div class="info-message">
                    <span>⏳ Starting summarization process...</span>
                </div>
                <div class="progress-bar">
                    <div class="progress" style="width: 5%;"></div>
                </div>
                """, unsafe_allow_html=True)
                progress_bar = st.empty() # Placeholder for updating progress bar

                try:
                    # 1. Initialize LLM
                    progress_bar.markdown("""
                    <div class="info-message">
                        <span>🔄 Initializing AI model ({model_name})...</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress" style="width: 15%;"></div>
                    </div>
                    """, unsafe_allow_html=True)
                    time.sleep(0.5)  # Visual delay

                    llm = ChatGroq(
                        model=model_name,
                        groq_api_key=GROQ_API_KEY,
                        max_tokens=max_tokens # Control output length
                    )

                    # 2. Process content based on URL type
                    is_youtube = "youtube" in url or "youtu.be" in url
                    docs = None # Initialize docs

                    if is_youtube:
                        progress_bar.markdown("""
                        <div class="info-message">
                            <span>🎬 Processing YouTube video... Extracting transcript...</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress" style="width: 30%;"></div>
                        </div>
                        """, unsafe_allow_html=True)

                        video_id = extract_youtube_id(url)
                        if not video_id:
                            st.markdown("""
                            <div class="error-message">
                                <span>⚠️ Could not extract YouTube video ID</span>
                            </div>
                            """, unsafe_allow_html=True)
                            st.stop()

                        # --- Call the updated get_youtube_transcript function ---
                        transcript = get_youtube_transcript(video_id)
                        # --- ---

                        if transcript:
                            progress_bar.markdown(f"""
                            <div class="success-message">
                                <span>✅ Transcript retrieved ({len(transcript):,} characters).</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress" style="width: 45%;"></div>
                            </div>
                            """, unsafe_allow_html=True)
                            docs = [Document(page_content=transcript, metadata={"source": url})]
                        else:
                            # Error messages are now handled inside get_youtube_transcript
                            st.stop() # Stop if transcript fetching failed

                    else: # Website
                        progress_bar.markdown("""
                        <div class="info-message">
                            <span>🌐 Loading and parsing website content...</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress" style="width: 30%;"></div>
                        </div>
                        """, unsafe_allow_html=True)

                        try:
                            loader = UnstructuredURLLoader(
                                urls=[url],
                                ssl_verify=False, # Keep SSL verification off as in original code
                                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
                            )
                            loaded_docs = loader.load()
                            if loaded_docs and loaded_docs[0].page_content: # Check if content exists
                                docs = loaded_docs
                                total_chars_loaded = sum(len(d.page_content) for d in docs)
                                progress_bar.markdown(f"""
                                <div class="success-message">
                                    <span>✅ Website content loaded ({len(docs)} element(s), {total_chars_loaded:,} characters).</span>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress" style="width: 45%;"></div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown("""
                                <div class="error-message">
                                    <span>❌ No text content found on the website or failed to parse.</span>
                                </div>
                                """, unsafe_allow_html=True)
                                st.stop()
                        except Exception as e:
                            st.markdown(f"""
                            <div class="error-message">
                                <span>❌ Error loading website: {str(e)}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            st.stop()

                    # 3. Split text if docs were loaded
                    if docs:
                        progress_bar.markdown("""
                        <div class="info-message">
                            <span>🔄 Splitting content into manageable chunks...</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress" style="width: 60%;"></div>
                        </div>
                        """, unsafe_allow_html=True)

                        text_splitter = RecursiveCharacterTextSplitter(
                            chunk_size=3000, # Adjust if needed based on model context limits & performance
                            chunk_overlap=200
                        )
                        split_docs = text_splitter.split_documents(docs)

                        # Display metrics
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">{len(split_docs)}</div>
                                <div class="metric-label">Text Chunks</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_b:
                            character_count = sum(len(doc.page_content) for doc in split_docs)
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">{character_count:,}</div>
                                <div class="metric-label">Characters</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_c:
                            word_count = sum(len(doc.page_content.split()) for doc in split_docs)
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">{word_count:,}</div>
                                <div class="metric-label">Words</div>
                            </div>
                            """, unsafe_allow_html=True)

                        # Content Preview Expander
                        with st.expander("📄 Content Preview (First 500 Characters)"):
                             st.markdown('<div class="content-preview">', unsafe_allow_html=True)
                             preview_text = docs[0].page_content[:500]
                             st.text(preview_text + "..." if len(docs[0].page_content) > 500 else preview_text)
                             st.markdown('</div>', unsafe_allow_html=True)

                        progress_bar.markdown("""
                        <div class="progress-bar">
                           <div class="progress" style="width: 70%;"></div>
                        </div>
                        """, unsafe_allow_html=True)


                        # 4. Summarize
                        progress_bar.markdown(f"""
                        <div class="info-message">
                            <span>🧠 Generating summary using '{chain_type}' method... (This may take a moment)</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress" style="width: 80%;"></div>
                        </div>
                        """, unsafe_allow_html=True)

                        # Select the appropriate chain type
                        if chain_type == "map_reduce":
                            chain = load_summarize_chain(
                                llm,
                                chain_type="map_reduce",
                                map_prompt=map_prompt,
                                combine_prompt=combine_prompt,
                                verbose=False # Set to True for debugging map/reduce steps
                            )
                        elif chain_type == "stuff":
                            # Basic check for 'stuff' method length limit (very approximate)
                            total_chars = sum(len(d.page_content) for d in split_docs)
                            est_tokens = total_chars / 4 # Rough estimate
                            context_window = 8192 if model_name == "llama3-8b-8192" else 32768 if model_name == "mixtral-8x7b-32768" else 8192 # Gemma approx

                            if est_tokens > (context_window * 0.85): # Leave buffer
                                st.warning(f"Content might be too long (~{est_tokens:.0f} tokens) for the 'stuff' method with {model_name}'s context window (~{context_window}). Summarization might fail or be truncated. Consider 'map_reduce' or 'refine'.")

                            chain = load_summarize_chain(
                                llm,
                                chain_type="stuff",
                                prompt=map_prompt, # 'stuff' uses a single prompt
                                verbose=False
                            )
                        else:  # refine
                            chain = load_summarize_chain(
                                llm,
                                chain_type="refine",
                                question_prompt=map_prompt, # Refine uses prompts differently
                                refine_prompt=combine_prompt,
                                verbose=False
                            )

                        try:
                            # Execute the chain within a spinner
                            with st.spinner(f"🤖 AI ({model_name}) is working on the summary..."):
                                start_time = time.time()
                                result = chain.invoke({"input_documents": split_docs})
                                end_time = time.time()
                                summary_time_taken = end_time - start_time

                            progress_bar.markdown(f"""
                            <div class="success-message">
                                <span>✅ Summarization complete! (Took {summary_time_taken:.2f} seconds)</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress" style="width: 100%;"></div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Display the summary
                            st.markdown('<div class="summary-container">', unsafe_allow_html=True)
                            st.subheader("📝 Generated Summary")
                            st.markdown(result["output_text"]) # Use markdown for better formatting

                            # Add metadata
                            summary_word_count = len(result["output_text"].split())
                            gen_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                            content_type_display = "YouTube Video" if is_youtube else "Website"

                            st.markdown(f"""
                            <hr>
                            <p style="text-align: right; font-size: 0.9rem; color: #555;">
                                ~{summary_word_count} words | {content_type_display} | Model: {model_name} | Method: {chain_type} | Max Tokens: {max_tokens} | Generated: {gen_time_str}
                            </p>
                            """, unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)

                        except Exception as e:
                            st.markdown(f"""
                            <div class="error-message">
                                <span>❌ Summarization failed: {str(e)}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            st.error("Suggestions: Try a different model (e.g., one with a larger context window like Mixtral if using 'stuff' on long text), use the 'map_reduce' or 'refine' method, shorten the summary length, or check the input URL content.")

                except Exception as e:
                    # Catch errors happening before summarization (e.g., LLM init)
                    st.markdown(f"""
                    <div class="error-message">
                        <span>❌ An unexpected error occurred during setup: {str(e)}</span>
                    </div>
                    """, unsafe_allow_html=True)
