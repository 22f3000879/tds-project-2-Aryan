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
    You are a scraper parser. Extract strictly valid JSON from this content.
    
    Keys: 
    - "question": Extract the EXACT instruction text from the page. 
    - "submit_url": The URL to POST the answer to.
    - "file_url": Look for "Download" links or "Scrape" links (hrefs). If none, null.

    OUTPUT RAW JSON ONLY.
    
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
        if "```" in content:
            content = content.split("```")[1].replace("json", "")
        return json.loads(content.strip())
    except Exception as e:
        print(f"Parse Error: {e}")
        return None

def solve_question(question: str, file_summary: str, page_content: str = ""):
    """
    Solves the question by generating and EXECUTING Python code.
    """
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS (JS Logic) ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    STRICT INSTRUCTIONS:
    1. **DECIDE THE GOAL (CRITICAL):**
       - Look at the "answer" field in the JSON sample inside the PAGE CONTENT.
       - **CASE A:** If it says "anything you want", simply write: `solution = "anything you want"`.
       - **CASE B:** If it says "the secret code" or similar, you MUST CALCULATE it from the scripts.

    2. **CALCULATION LOGIC (For CASE B only):**
       - Look at the "IMPORTED FILE" (e.g. `demo-scrape.js`).
       - If it calls `emailNumber()`, you must define `email_number` and call it.
       - **NO HALLUCINATIONS:** Do NOT invent functions (like `demo2_key`). Do NOT add random math (like `* 7919`) unless it is explicitly in the text.
       - Translate the logic from `utils.js` exactly.
    
    3. **SYNCHRONOUS ONLY:** No `async`/`await`. Use `hashlib` for sha1.
    4. **NO NETWORK:** Do not use `requests`.

    5. **OUTPUT:**
       - Define a variable `solution` with the final answer.
       - Return ONLY the Python code block.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Extract Python Code
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        if code_match:
            code = code_match.group(1)
        else:
            code = content.replace("```python", "").replace("```", "")
            
        print(f"DEBUG: Generated Python Code:\n{code}")
        
        # --- SCOPE FIX ---
        execution_scope = {
            "__builtins__": __builtins__,
            "import": __import__,
            "email": STUDENT_EMAIL
        }
        
        try:
            exec(code, execution_scope, execution_scope)
        except Exception as e:
            print(f"Execution Error: {e}")
            traceback.print_exc()
            return "Error executing code"
            
        # Retrieve Solution
        answer = execution_scope.get("solution")
        print(f"DEBUG: Execution Result (solution): {answer}")
        
        return answer

    except Exception as e:
        print(f"Solve Error: {e}")
        return "Error"
