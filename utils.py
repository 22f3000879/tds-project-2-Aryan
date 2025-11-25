import re
import base64
import httpx
from io import BytesIO
from pypdf import PdfReader
import pandas as pd

async def fetch_and_decode_page(url: str):
    """
    Fetches the HTML and uses Regex to find the 'atob(...)' hidden content.
    Simulates what a browser does without actually running a browser.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text

    # --- THE FIX ---
    # We changed the capture group to ([^`'"]+)
    # This means: "Capture absolutely anything that is NOT a quote character"
    # This automatically includes newlines, which broke the previous version.
    pattern = r'atob\s*\(\s*[`\'"]([^`\'"]+)[`\'"]\s*\)'
    
    match = re.search(pattern, html)

    if match:
        encoded_content = match.group(1)
        try:
            # Decode the base64 string to get the real HTML/Text
            decoded_bytes = base64.b64decode(encoded_content)
            decoded_text = decoded_bytes.decode('utf-8')
            return decoded_text
        except Exception as e:
            print(f"Error decoding Base64: {e}")
            return html # Fallback to raw HTML
    
    return html

def parse_file_content(file_url: str):
    """
    Downloads and extracts text from PDFs or CSVs for the LLM to read.
    """
    try:
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
            return f"CSV CONTENT (First 50 rows):\n{df.head(50).to_string()}"
        
        else:
            return f"TEXT FILE CONTENT:\n{response.text[:5000]}"
            
    except Exception as e:
        return f"Error reading file: {e}"
