import json
import re
import traceback
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, STUDENT_EMAIL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
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

def sanitize_code(code: str, context: str):
    """
    Cleans code and neutralizes hallucinations by checking against the source context.
    """
    # 1. Remove Network stuff
    code = re.sub(r'^import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^import urllib.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    
    # 2. NEUTRALIZE HALLUCINATED MATH (The Critical Fix)
    # The LLM often hallucinates "demo2_key" logic involving 7919 and 12345.
    # If the code uses 7919 but the downloaded files DO NOT contain 7919...
    if "7919" in code and "7919" not in context:
        print("DEBUG: Neutralizing hallucinated math (7919 -> 1)")
        # We replace the numbers with Identity values (x * 1 + 0 = x)
        # This preserves the variable names the LLM chose, preventing syntax errors
        code = code.replace("7919", "1")
        code = code.replace("12345", "0")
        code = code.replace("% 100000000", "")
        
    # 3. Function Replacement (Safety)
    if "demo2_key" in code and "demo2_key" not in context:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)

    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS / TRANSCRIPTS ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    STRICT RULES:
    1. **NO NETWORK:** Do NOT use `requests`. Use `io.StringIO(file_summary)` for CSVs.
    2. **NO HALLUCINATIONS:** Do NOT use `demo2_key` or `7919` unless explicitly in the text.
    3. **SYNCHRONOUS ONLY:** No `async`/`await`.
    4. **DONT USE ANY FORMULA FROM YOUR MEMMORY OR any prior knowledge IF YOU SEE ANY SIMILAR QUESTIONS. ALWAY Trust whats provided above:** Dont be oversmart
    5. **WARNING:** Do not add math that is not in the Source File. If the Source File only does `sha1` and `slice`, then your Python must ONLY do `sha1` and `slice`
    
    SCENARIO DETECTOR:
    
    **A. VISUALIZATION (Charts):**
       - If asked to plot:
         1. Use `matplotlib.pyplot`.
         2. Save plot to `io.BytesIO`.
         3. `solution = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode('utf-8')`
    
    **B. MACHINE LEARNING / ANALYSIS:**
       - If asked to cluster or regress:
         1. Use `sklearn` (e.g., KMeans, LinearRegression).
         2. Use `pandas` to clean data first.
         3. `solution = result`
    
    **C. HYBRID TASK (Audio + CSV + JS):**
       - **Step 1 (Rule):** Read "AUDIO TRANSCRIPT".
       - **Step 2 (Cutoff):** If transcript/page mentions `emailNumber` or `cutoff`, you MUST calculate it using the JS logic found in "IMPORTED FILE" (usually `utils.js`). Translate JS to Python 1:1.
       - **Step 3 (Data):** Read CSV from `file_summary` using `pd.read_csv(io.StringIO(file_summary))`.
       - **Step 4 (Clean):** Ensure columns are numeric: `df[0] = pd.to_numeric(df[0], errors='coerce')`.
       - **Step 5 (Solve):** Filter and sum. 
       - **CRITICAL:** `solution = int(result)` (Convert numpy int to python int).
    
    **D. JS LOGIC (Secret Code):**
       - Implement JS logic (from "IMPORTED FILE") in Python.
       - Use `hashlib.sha1` if needed.
       - Do NOT use `demo2_key` or `7919` unless seen in text.
    
    **E. SIMPLE PLACEHOLDER:**
       - If sample says "anything", `solution = "anything you want"`.

    **OUTPUT:**
    - **MUST** define a variable named `solution` at the end.
    - Return ONLY Python code.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Extract Code
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        code = code_match.group(1) if code_match else content.replace("```python", "").replace("```", "")
        
        # --- INTELLIGENT SANITIZATION (The Fix) ---
        # We pass file_summary to check if 7919 is real or hallucinated
        code = sanitize_code(code, file_summary)
        print(f"DEBUG: Final Python Code:\n{code}")
        
        # Variables for the script
        scope = {
            "__builtins__": __builtins__,
            "import": __import__,
            "email": STUDENT_EMAIL,
            "file_summary": file_summary, 
            "page_content": page_content
        }
        
        exec(code, scope, scope)
        
        # --- SAFETY NET: Find the answer even if variable name is wrong ---
        solution = None
        for var in ["solution", "secret_code", "answer", "result"]:
            if var in scope:
                solution = scope[var]
                break
        
        # Handle numpy types
        if hasattr(solution, 'item'): 
            solution = solution.item()
            
        if solution is None:
            print("ERROR: No solution variable found.")
            
        return solution

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
