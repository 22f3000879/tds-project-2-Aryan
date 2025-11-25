import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
    """
    Step 1: Look at the decoded HTML and extract the structure.
    """
    prompt = f"""
    You are a precise scraper parser. 
    Analyze this HTML/Text content.
    
    Extract strictly valid JSON with these keys:
    - "question": The ACTUAL problem to solve (e.g. "What is the sum...", "Find the code...").
    - "submit_url": The URL found in the text where the answer must be POSTed.
    - "file_url": Look for <a href="..."> links. If a file (PDF/CSV) needs to be downloaded, put the URL here. If none, null.
    
    CRITICAL INSTRUCTION:
    - Output ONLY the raw JSON string.
    - Do NOT write any conversational text.
    
    CONTENT:
    {decoded_html[:15000]}
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Regex to find JSON block
        code_block_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
        if code_block_match:
            clean_json = code_block_match.group(1)
        else:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                clean_json = content[start : end + 1]
            else:
                clean_json = content

        return json.loads(clean_json)

    except Exception as e:
        print(f"Parse Error: {e}")
        return None

# --- UPDATE START: Added page_content argument ---
def solve_question(question: str, file_summary: str, page_content: str = ""):
    """
    Step 2: Answer the question based on the question text, file content, AND page content.
    """
    prompt = f"""
    You are a Data Science assistant. 
    Calculate the answer to this question.
    
    QUESTION: {question}
    
    --- PAGE CONTENT (The answer might be written here) ---
    {page_content[:20000]} 
    
    --- DATA CONTEXT (From downloaded files) ---
    {file_summary}
    
    INSTRUCTION:
    - If the question asks for a number, return just the number.
    - If the question asks for text/code found on the page, extract it exactly.
    - Return STRICT JSON format: {{ "answer": <YOUR_ANSWER> }}
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        content = content.replace("```json", "").replace("```", "").strip()
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start : end + 1]
            
        return json.loads(content)["answer"]
    except Exception as e:
        print(f"Solve Error: {e}")
        return None
# --- UPDATE END ---
