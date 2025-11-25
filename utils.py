import re
import base64
import httpx
from io import BytesIO
from pypdf import PdfReader
import pandas as pd
# Import your email to fix the $EMAIL variable
from config import STUDENT_EMAIL 

async def fetch_and_decode_page(url: str):
    """
    Fetches HTML, finds hidden content via Regex, and fixes variables like $EMAIL.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text

    # Regex to capture content inside atob(`...`) or atob("...")
    pattern = r'atob\s*\(\s*[`\'"]([^`\'"]+)[`\'"]\s*\)'
    match = re.search(pattern, html)

    if match:
        encoded_content = match.group(1)
        try:
            decoded_bytes = base64.b64decode(encoded_content)
            decoded_text = decoded_bytes.decode('utf-8')
            
            # --- FIX: Manually replace $EMAIL with the real email ---
            # This simulates the JavaScript execution
            decoded_text = decoded_text.replace("$EMAIL", STUDENT_EMAIL)
            
            return decoded_text
        except Exception as e:
            print(f"Error decoding Base64: {e}")
            return html 
    
    return html

def parse_file_content(file_url: str):
    """
    Downloads content. Handles PDFs, CSVs, AND generic HTML scraping.
    """
    try:
        response = httpx.get(file_url, timeout=30)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get("Content-Type", "").lower()

        if "pdf" in content_type or file_url.endswith(".pdf"):
            reader = PdfReader(BytesIO(response.content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return f"PDF CONTENT:\n{text}"
        
        elif "csv" in content_type or file_url.endswith(".csv"):
            df = pd.read_csv(BytesIO(response.content))
            return f"CSV CONTENT (First 50 rows):\n{df.head(50).to_string()}"
        
        else:
            # Fallback for HTML/Text scraping
            # This is what handles the "Scrape this page" link
            return f"SCRAPED CONTENT:\n{response.text[:10000]}"
            
    except Exception as e:
        return f"Error reading file: {e}"
