import re
import base64
import httpx
from io import BytesIO
from pypdf import PdfReader
from urllib.parse import urljoin
from config import STUDENT_EMAIL, OPENAI_API_KEY
from openai import OpenAI

openai_client = OpenAI(api_key=OPENAI_API_KEY)

def transcribe_audio(audio_url):
    try:
        print(f"DEBUG: Transcribing audio from {audio_url}...", flush=True)
        response = httpx.get(audio_url, timeout=30)
        response.raise_for_status()
        audio_file = BytesIO(response.content)
        audio_file.name = "audio.mp3" 
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1", file=audio_file
        )
        return f"\n\n--- AUDIO TRANSCRIPT ({audio_url}) ---\n{transcript.text}\n"
    except Exception as e:
        print(f"Audio transcription failed: {e}", flush=True)
        return ""

def try_decode_base64(text: str):
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
    extra_content = ""
    
    # 1. Scripts/Imports
    refs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text) + \
           re.findall(r'from\s+["\']([^"\']+)["\']', text)
    for ref in refs:
        full_url = urljoin(base_url, ref)
        try:
            resp = httpx.get(full_url, timeout=10)
            extra_content += f"\n\n--- IMPORTED FILE ({ref}) ---\n{resp.text}"
            nested = re.findall(r'from\s+["\']([^"\']+)["\']', resp.text)
            for n in nested:
                n_url = urljoin(full_url, n)
                extra_content += f"\n\n--- NESTED IMPORT ({n}) ---\n{httpx.get(n_url, timeout=10).text}"
        except: pass

    # 2. Audio (Aggressive Search)
    # Finds href="file.opus", src="file.opus", "file.opus"
    audio_extensions = r'[^"\'=\s]+\.(?:opus|mp3|wav)'
    audio_matches = re.findall(audio_extensions, text)
    
    # Filter valid URLs and remove duplicates
    audio_matches = list(set(audio_matches))
    
    for src in audio_matches:
        # Ignore common false positives like library names if any
        if "http" not in src and "/" not in src: continue 
        
        full_url = urljoin(base_url, src)
        extra_content += transcribe_audio(full_url)
            
    return extra_content

async def fetch_and_decode_page(url: str):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        extras = fetch_external_resources(url, resp.text)
        return try_decode_base64(resp.text + extras) + "\nRaw Extras:\n" + extras

def parse_file_content(file_url: str):
    try:
        if "$EMAIL" in file_url: file_url = file_url.replace("$EMAIL", STUDENT_EMAIL)
        
        # --- PRE-FETCH AUDIO ---
        # If the "file" itself is an audio file (common in Step 5)
        if file_url.endswith((".opus", ".mp3", ".wav")):
            return transcribe_audio(file_url)
            
        resp = httpx.get(file_url, timeout=30)
        
        # Image Handling
        if file_url.endswith(('.png', '.jpg', '.jpeg')):
            b64 = base64.b64encode(resp.content).decode('utf-8')
            return f"IMAGE_BASE64:{b64}"
            
        # CSV Handling
        if "csv" in resp.headers.get("Content-Type", "") or file_url.endswith(".csv"):
            return resp.text 
        
        main_text = resp.text
        extras = fetch_external_resources(file_url, main_text)
        return f"SCRAPED CONTENT:\n{try_decode_base64(main_text + extras)[:20000]}"
    except Exception as e:
        return f"Error: {e}"
