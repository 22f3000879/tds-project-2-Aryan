import re
import base64
import httpx
from io import BytesIO
from pypdf import PdfReader
import pandas as pd
from urllib.parse import urljoin
from config import STUDENT_EMAIL, OPENAI_API_KEY
from openai import OpenAI

# Initialize client for Whisper
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def transcribe_audio(audio_url):
    """
    Downloads audio and transcribes it using OpenAI Whisper.
    """
    try:
        print(f"DEBUG: Transcribing audio from {audio_url}...", flush=True)
        response = httpx.get(audio_url, timeout=30)
        response.raise_for_status()
        
        # OpenAI requires a filename to know the format
        audio_file = BytesIO(response.content)
        audio_file.name = "audio.mp3" # Generic extension usually works, or match the url

        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
        return f"\n\n--- AUDIO TRANSCRIPT ({audio_url}) ---\n{transcript.text}\n"
    except Exception as e:
        print(f"Audio transcription failed: {e}", flush=True)
        return "\n[Audio Transcription Failed]"

def try_decode_base64(text: str):
    """
    Helper to find and decode base64 strings in any text.
    """
    candidates = re.findall(r'[`\'"]([A-Za-z0-9+/=\s]{100,})[`\'"]', text)
    if candidates:
        encoded = max(candidates, key=len)
        try:
            decoded = base64.b64decode(encoded).decode('utf-8')
            return decoded.replace("$EMAIL", STUDENT_EMAIL)
        except:
            pass
    return text

def fetch_external_resources(base_url, text):
    """
    Finds scripts, imports, AND AUDIO to enrich the context.
    """
    extra_content = ""
    
    # 1. Scripts and Imports
    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text)
    js_imports = re.findall(r'from\s+["\']([^"\']+)["\']', text)
    
    # 2. Audio Files (The Fix for Step 3)
    audio_srcs = re.findall(r'<audio[^>]+src=["\']([^"\']+)["\']', text)
    
    # Handle Scripts
    for ref in script_srcs + js_imports:
        full_url = urljoin(base_url, ref)
        try:
            resp = httpx.get(full_url, timeout=10)
            script_text = resp.text
            extra_content += f"\n\n--- IMPORTED FILE ({ref}) ---\n{script_text}"
            
            # Recursive import check
            nested_imports = re.findall(r'from\s+["\']([^"\']+)["\']', script_text)
            for nested in nested_imports:
                nested_url = urljoin(full_url, nested)
                try:
                    nested_resp = httpx.get(nested_url, timeout=10)
                    extra_content += f"\n\n--- NESTED IMPORT ({nested}) ---\n{nested_resp.text}"
                except:
                    pass
        except:
            pass

    # Handle Audio
    for src in audio_srcs:
        full_url = urljoin(base_url, src)
        extra_content += transcribe_audio(full_url)
            
    return extra_content

async def fetch_and_decode_page(url: str):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
    
    # Fetch scripts AND transcribe audio
    extras = fetch_external_resources(url, html)
    
    decoded_html = try_decode_base64(html)
    decoded_extras = try_decode_base64(extras)
    
    return decoded_html + "\n" + decoded_extras + "\nRaw Extras:\n" + extras

def parse_file_content(file_url: str):
    try:
        if "$EMAIL" in file_url:
            file_url = file_url.replace("$EMAIL", STUDENT_EMAIL)

        response = httpx.get(file_url, timeout=30)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()

        if "pdf" in content_type or file_url.endswith(".pdf"):
            reader = PdfReader(BytesIO(response.content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return f"PDF CONTENT:\n{text}"
        
        elif "csv" in content_type or file_url.endswith(".csv"):
            df = pd.read_csv(BytesIO(response.content))
            return f"CSV CONTENT:\n{df.to_string()}" # Get full CSV for summing
        
        else:
            main_text = response.text
            extras = fetch_external_resources(file_url, main_text)
            combined_text = main_text + extras
            decoded = try_decode_base64(combined_text)
            return f"SCRAPED CONTENT:\n{decoded[:20000]}"

    except Exception as e:
        return f"Error reading file: {e}"
