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
        return f"\n\n--- AUDIO TRANSCRIPT ---\n{transcript.text}\n"
    except Exception as e:
        print(f"Audio error: {e}")
        return "\n--- AUDIO TRANSCRIPT ---\n(Transcription failed)\n"

def try_decode_base64(text: str):
    candidates = re.findall(r'[`\'"]([A-Za-z0-9+/=\s]{100,})[`\'"]', text)
    if candidates:
        encoded = max(candidates, key=len)
        try:
            decoded = base64.b64decode(encoded).decode('utf-8')
            return decoded.replace("$EMAIL", STUDENT_EMAIL)
        except: pass
    return text

def fetch_external_resources(base_url, html_content):
    assets = ""
    patterns = [
        r'src=["\']([^"\']+\.(?:js|png|jpg|jpeg|opus|mp3|wav|zip))["\']',
        r'href=["\']([^"\']+\.(?:js|png|jpg|jpeg|opus|mp3|wav|csv|json|yaml|md|zip|pdf))["\']'
    ]
    urls = []
    for p in patterns: urls.extend(re.findall(p, html_content))
    urls = list(set(urls))
    
    for relative_url in urls:
        full_url = urljoin(base_url, relative_url)
        filename = full_url.split("/")[-1]
        try:
            if not filename or filename.startswith("?"): continue
            
            # AUDIO -> Transcribe immediately
            if filename.endswith(('.opus', '.mp3', '.wav')):
                assets += transcribe_audio(full_url)
                continue

            resp = httpx.get(full_url, timeout=20)
            if resp.status_code != 200: continue
            
            # BINARY (Images, ZIPs) -> Base64
            if filename.endswith(('.png', '.jpg', '.jpeg', '.zip')):
                b64 = base64.b64encode(resp.content).decode('utf-8')
                assets += f"\n--- BINARY FILE: {filename} ---\nBASE64:{b64}\n"
            
            # PDF -> Text
            elif filename.endswith('.pdf'):
                try:
                    reader = PdfReader(BytesIO(resp.content))
                    text = "\n".join([p.extract_text() for p in reader.pages])
                    assets += f"\n--- PDF TEXT: {filename} ---\n{text}\n"
                except: pass

            # TEXT DATA
            else:
                text_content = resp.text
                if filename.endswith(".js"):
                    nested = re.findall(r'from\s+["\']([^"\']+)["\']', text_content)
                    for n in nested:
                        try:
                            assets += f"\n--- JS IMPORT: {n} ---\n{httpx.get(urljoin(full_url, n), timeout=10).text}\n"
                        except: pass
                assets += f"\n--- DATA FILE: {filename} ---\n{text_content[:25000]}\n"
        except: pass
            
    return assets

async def fetch_and_decode_page(url: str):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        extras = fetch_external_resources(url, resp.text)
        return try_decode_base64(resp.text + extras) + "\nRaw Extras:\n" + extras

def parse_file_content(file_url: str):
    try:
        if "$EMAIL" in file_url: file_url = file_url.replace("$EMAIL", STUDENT_EMAIL)
        
        if file_url.endswith(('.opus', '.mp3', '.wav')): return transcribe_audio(file_url)
        
        resp = httpx.get(file_url, timeout=30)
        
        if file_url.endswith(('.png', '.jpg', '.zip')):
            b64 = base64.b64encode(resp.content).decode('utf-8')
            return f"BINARY_BASE64:{b64}"
            
        return f"FILE CONTENT:\n{resp.text[:20000]}"
    except Exception as e: return f"Error: {e}"
