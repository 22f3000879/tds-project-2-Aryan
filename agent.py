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
    
    --- DATA / SCRIPTS / TRANSCRIPTS (The Source of Truth) ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    GENERAL RULES (Apply to ALL Steps):
    1. **NO NETWORK:** Do NOT use `requests`. Calculate everything locally.
    2. **SYNCHRONOUS ONLY:** No `async` or `await`.
    3. **NO HALLUCINATIONS:** - **CRITICAL:** Do NOT use `demo2_key`, `7919`, or `12345` unless you explicitly see them in the "DATA" section above.
       - Only implement logic that is visibly present in the text.
    
    SCENARIO LOGIC (Detect which case applies):
    
    **SCENARIO A: The "Anything" Answer**
    - IF the JSON sample in the page content says `"answer": "anything"` (or similar placeholder), simply write:
      `solution = "anything you want"`
    
    **SCENARIO B: JavaScript Logic (The Secret Code)**
    - IF the "IMPORTED FILE" contains JavaScript logic (like `emailNumber`):
      1. Read the JS logic carefully.
      2. If `utils.js` defines `emailNumber` as just `int(sha1(email)[:4], 16)`, then WRITE THAT EXACTLY.
      3. Do NOT add extra math operations that aren't there.
    
    **SCENARIO C: Audio + CSV**
    - IF there is an "AUDIO TRANSCRIPT", read the rule from it (e.g., "Sum numbers > X").
    - IF there is "CSV CONTENT", parse the data.
    - Combine them: Calculate the cutoff, filter the CSV, compute the result.

    **OUTPUT:**
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
