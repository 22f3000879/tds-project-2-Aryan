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
    # We use the math formula backup for stability, but we can log this.
    return "\n(Audio skipped - using formula)\n"

def try_decode_base64(text: str):
    candidates = re.findall(r'[`\'"]([A-Za-z0-9+/=\s]{100,})[`\'"]', text)
    if candidates:
        encoded = max(candidates, key=len)
        try:
            return base64.b64decode(encoded).decode('utf-8').replace("$EMAIL", STUDENT_EMAIL)
        except: pass
    return text

def fetch_external_resources(base_url, html_content):
    assets = ""
    # Find CSV/JSON links
    urls = re.findall(r'href=["\']([^"\']+\.(?:csv|json|txt))["\']', html_content)
    for relative_url in set(urls):
        full_url = urljoin(base_url, relative_url)
        try:
            resp = httpx.get(full_url, timeout=20)
            if resp.status_code == 200:
                assets += f"\n\n--- FILE CONTENT: {relative_url} ---\n{resp.text[:20000]}\n"
        except: pass
    return assets

async def fetch_and_decode_page(url: str):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        extras = fetch_external_resources(url, resp.text)
        return try_decode_base64(resp.text) + "\n" + extras

def parse_file_content(file_url: str):
    try:
        if "$EMAIL" in file_url: file_url = file_url.replace("$EMAIL", STUDENT_EMAIL)
        
        # CRITICAL: For CSVs, return the raw text directly.
        if file_url.endswith((".csv", ".json", ".txt")):
            resp = httpx.get(file_url, timeout=30)
            return resp.text 
            
        # For Images/ZIPs, return Base64
        if file_url.endswith(('.png', '.jpg', '.zip')):
            resp = httpx.get(file_url, timeout=30)
            b64 = base64.b64encode(resp.content).decode('utf-8')
            return f"BINARY_BASE64:{b64}"
            
        return ""
    except Exception as e: return f"Error: {e}"
