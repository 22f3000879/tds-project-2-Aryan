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
    Analyze this HTML/Text content (which was decoded from a hidden script).
    
    Extract strictly valid JSON with these keys:
    - "question": The main question text.
    - "submit_url": The URL found in the text where the answer must be POSTed.
    - "file_url": Look for <a href="..."> links. If a file (PDF/CSV) needs to be downloaded, put the URL here. If none, null.
    
    CRITICAL INSTRUCTION:
    - Output ONLY the raw JSON string.
    - Do NOT write any conversational text, analysis, or explanations.
    - Do NOT wrap the output in markdown code blocks (like ```json). Just the raw JSON.
    
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
        
        # --- ROBUST EXTRACTION STRATEGY ---
        
        # Strategy A: Check if it's wrapped in Markdown code blocks
        # Regex finds content between ```json AND ``` (dotall mode)
        code_block_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
        if code_block_match:
            # If found, take the content inside the block
            clean_json = code_block_match.group(1)
        else:
            # Strategy B: No code blocks? Just find the first { and last }
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                clean_json = content[start : end + 1]
            else:
                clean_json = content # Hope for the best

        return json.loads(clean_json)

    except Exception as e:
        print(f"Parse Error: {e}")
        print(f"Raw Content that failed: {content}")
        return None

def solve_question(question: str, file_summary: str):
    """
    Step 2: Answer the question based on the question text and file content.
    """
    prompt = f"""
    You are a Data Science assistant. 
    Calculate the answer to this question.
    
    QUESTION: {question}
    
    DATA CONTEXT:
    {file_summary}
    
    Return STRICT JSON format:
    {{
        "answer": <YOUR_ANSWER_HERE>
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Simple cleanup for the solver response
        content = content.replace("```json", "").replace("```", "").strip()
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start : end + 1]
            
        return json.loads(content)["answer"]
    except Exception as e:
        print(f"Solve Error: {e}")
        return None
