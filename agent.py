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
    
    GENERAL RULES:
    1. **NO NETWORK:** Do NOT use `requests`. Calculate everything locally.
    2. **NO HALLUCINATIONS:** Only use logic/numbers found in the provided text. Do not invent functions (like `demo2_key`) or magic numbers (like `7919`) unless they are explicitly in the text.
    
    DYNAMIC LOGIC (Apply the rule that fits the data):
    
    **CASE A: JS Logic / Secret Code**
    - IF you see JavaScript code (e.g. in "IMPORTED FILE"), translate that logic 1:1 into Python.
    - IF `utils.js` defines a function, write a Python equivalent.
    - EXECUTE the translated function to get the secret.
    
    **CASE B: Audio Instructions + Data**
    - IF there is an "AUDIO TRANSCRIPT", read it carefully. It contains the math rule (e.g. "Sum numbers > 500").
    - IF there is "CSV CONTENT", parse the data and apply the math rule from the transcript.
    
    **CASE C: Simple JSON Submission**
    - IF the page provides a JSON sample where `"answer": "anything"`, simply set `solution = "anything you want"`.
    - IF the page asks for a simple text extraction, just assign that text to `solution`.

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
