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
        # Check if it's actually an image (fallback logic)
        if audio_url.endswith(('.png', '.jpg', '.jpeg')):
            return f"IMAGE_URL:{audio_url}"
            
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
        print(f"Audio/Image fetch failed: {e}", flush=True)
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
    # Scripts/Imports
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

    # Audio & Images
    media_srcs = re.findall(r'<audio[^>]+src=["\']([^"\']+)["\']', text) + \
                 re.findall(r'src=["\']([^"\']+\.(?:png|jpg|jpeg))["\']', text)
                 
    for src in media_srcs:
        extra_content += transcribe_audio(urljoin(base_url, src))
            
    return extra_content

async def fetch_and_decode_page(url: str):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        extras = fetch_external_resources(url, resp.text)
        return try_decode_base64(resp.text + extras) + "\nRaw Extras:\n" + extras

def parse_file_content(file_url: str):
    try:
        if "$EMAIL" in file_url: file_url = file_url.replace("$EMAIL", STUDENT_EMAIL)
        resp = httpx.get(file_url, timeout=30)
        
        # --- IMAGE HANDLING ---
        if file_url.endswith(('.png', '.jpg', '.jpeg')):
            # Return as Base64 string so Python can read it
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
