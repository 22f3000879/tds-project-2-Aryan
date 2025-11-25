import json
import re
import traceback
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, STUDENT_EMAIL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
    """
    Analyzes the task to extract the question and URLs.
    """
    prompt = f"""
    You are a scraper parser. Extract strictly valid JSON.
    Keys: "question", "submit_url", "file_url".
    CONTENT: {decoded_html[:15000]}
    """
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0
        )
        content = response.choices[0].message.content.strip()
        if "```" in content: content = content.split("```")[1].replace("json", "")
        return json.loads(content.strip())
    except: return None

def sanitize_code(code: str):
    """
    Removes network calls and async/await to prevent crashes.
    """
    code = re.sub(r'^import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^import urllib.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    # Guardrail against specific hallucinations if the source text doesn't support them
    if "demo2_key" in code and "7919" not in code: 
        code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)
    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    """
    Solves the question by generating Python code.
    The data is PASSED directly into the scope, so the LLM doesn't need to copy-paste it.
    """
    
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- AVAILABLE VARIABLES (Already defined in your environment) ---
    1. `email` (str): The student email.
    2. `file_summary` (str): Contains the CSV data, JS code, or Audio Transcript.
    3. `page_content` (str): The HTML text of the page.
    
    --- PREVIEW OF DATA ---
    {file_summary[:2000]} ... (Truncated view, but full variable is available)
    
    STRICT LOGIC (Detect which rule applies):
    
    1. **IF AUDIO TRANSCRIPT EXISTS:**
       - The logic is in the transcript (e.g. "Sum numbers > X").
       - The CSV data is inside the `file_summary` variable.
       - Use `io.StringIO(file_summary)` to read it with pandas.
       - If `emailNumber()` is mentioned, find its logic in `file_summary` (look for 'IMPORTED FILE').
       - `solution = int(result)`
    
    2. **IF JS LOGIC EXISTS (Secret Code):**
       - If `file_summary` contains JavaScript (e.g. `emailNumber`), translate that logic 1:1 to Python.
       - **DO NOT** use `demo2_key` or `7919` unless you explicitly see them in the text.
       - Use `hashlib` for sha1.
    
    3. **IF SIMPLE PLACEHOLDER:**
       - If `page_content` has a JSON sample with `"answer": "anything"`, set:
         `solution = "anything you want"`

    **OUTPUT:**
    - Write code that defines `solution`.
    - Return ONLY the Python code block.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Extract Code
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        code = code_match.group(1) if code_match else content.replace("```python", "").replace("```", "")
        
        code = sanitize_code(code)
        print(f"DEBUG: Sanitized Python Code:\n{code}")
        
        # --- CRITICAL: PASS DATA AS VARIABLES ---
        scope = {
            "__builtins__": __builtins__,
            "import": __import__,
            "email": STUDENT_EMAIL,
            "file_summary": file_summary, # <--- The CSV/JS data is passed here!
            "page_content": page_content
        }
        
        exec(code, scope, scope)
        return scope.get("solution")

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
