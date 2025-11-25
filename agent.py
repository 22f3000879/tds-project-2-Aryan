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
    
    # Check if the forbidden numbers exist in the source text
    has_7919 = "7919" in file_summary
    
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS / TRANSCRIPTS (The Source of Truth) ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    STRICT INSTRUCTIONS:
    1. **SCENARIO A (Simple Answer):**
       - If JSON sample says `"answer": "anything"`, write: `solution = "anything you want"`.
    
    2. **SCENARIO B (JS Logic):**
       - Translate the JavaScript in "IMPORTED FILE" to Python 1:1.
       - **HALLUCINATION CHECK:**
         - The number '7919' appears in the provided text? {'YES' if has_7919 else 'NO'}.
         - If NO, do **NOT** use 7919 in your code. Do **NOT** define `demo2_key`.
         - Just implement `sha1` and the `emailNumber` logic exactly as seen.
    
    3. **SCENARIO C (Audio + CSV):**
       - Read "AUDIO TRANSCRIPT" for the rule (e.g. "sum > X").
       - Parse "CSV CONTENT".
       - Calculate the result.
       - **CRITICAL:** Convert final result to `int()` or `str()` (No numpy types).

    4. **OUTPUT:**
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
        
        # --- GUARDRAIL: Prevent Hallucinated Math ---
        if "7919" in code and not has_7919:
            print("WARNING: LLM hallucinated 7919. Removing forbidden code.")
            # We forcibly remove the hallucinated function call if the number wasn't in the source
            code = code.replace("demo2_key", "email_number") 
            code = code.replace("* 7919", "") 
            code = code.replace("+ 12345", "")
            code = code.replace("% 100000000", "")
        # --------------------------------------------
        
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
