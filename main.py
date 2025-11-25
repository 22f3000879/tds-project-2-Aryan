from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
import httpx
import re
from urllib.parse import urljoin
from config import STUDENT_EMAIL, STUDENT_SECRET
from utils import fetch_and_decode_page, parse_file_content
from agent import analyze_task, solve_question

app = FastAPI()

def clean_extracted_url(url: str):
    """
    Removes HTML tags like <span class="origin"></span> if the LLM accidentally extracts them.
    """
    if not url:
        return None
    # Remove any HTML tags
    clean = re.sub(r'<[^>]+>', '', url)
    return clean.strip()

async def run_quiz_process(start_url: str):
    """
    The main loop that runs in the background.
    """
    current_url = start_url
    step_count = 0
    
    while current_url and step_count < 10:
        print(f"--- STEP {step_count + 1} processing {current_url} ---")
        
        # 1. Get the Hidden Question AND Page Content
        decoded_text = await fetch_and_decode_page(current_url)
        print(f"DEBUG: Page Content (First 500 chars): {decoded_text[:500]}...")

        # 2. Parse it with LLM
        task_data = analyze_task(decoded_text)
        if not task_data:
            print("Failed to parse task.")
            break
            
        print(f"Task Found: {task_data}")
        
        # 3. Handle Files (if any)
        file_summary = "No files."
        if task_data.get("file_url"):
            raw_f_url = task_data["file_url"]
            # CLEAN THE URL
            f_url = clean_extracted_url(raw_f_url)
            
            if not f_url.startswith("http"):
                f_url = urljoin(current_url, f_url)
            
            print(f"Downloading file: {f_url}")
            file_summary = parse_file_content(f_url)

        # 4. Solve 
        answer = solve_question(task_data["question"], file_summary, decoded_text)
        print(f"Calculated Answer: {answer}")
        
        # 5. Submit
        submit_payload = {
            "email": STUDENT_EMAIL,
            "secret": STUDENT_SECRET,
            "url": current_url,
            "answer": answer
        }
        
        raw_submit_url = task_data["submit_url"]
        # CLEAN THE URL
        submit_url = clean_extracted_url(raw_submit_url)
        
        if submit_url and not submit_url.startswith("http"):
            submit_url = urljoin(current_url, submit_url)
        
        try:
            print(f"Submitting to {submit_url}...")
            async with httpx.AsyncClient() as client:
                resp = await client.post(submit_url, json=submit_payload, timeout=30)
                try:
                    result = resp.json()
                except:
                    print(f"Non-JSON response: {resp.text}")
                    break

                print(f"Submission Result: {result}")
                
                if result.get("correct"):
                    if result.get("url"):
                        current_url = result["url"]
                        step_count += 1
                    else:
                        print("Quiz Completed Successfully!")
                        break
                else:
                    print(f"Wrong Answer. Reason: {result.get('reason')}")
                    break
                    
        except Exception as e:
            print(f"Submission failed: {e}")
            break

@app.post("/")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if data.get("secret") != STUDENT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid Secret")
    
    background_tasks.add_task(run_quiz_process, data.get("url"))
    return {"message": "Quiz processing started", "status": "ok"}

@app.get("/")
def health_check():
    return {"status": "active", "student": STUDENT_EMAIL}
