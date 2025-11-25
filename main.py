from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
import httpx
from config import STUDENT_EMAIL, STUDENT_SECRET
from utils import fetch_and_decode_page, parse_file_content
from agent import analyze_task, solve_question

app = FastAPI()

async def run_quiz_process(start_url: str):
    """
    The main loop that runs in the background.
    """
    current_url = start_url
    step_count = 0
    
    # Run for a max of 5 steps to prevent infinite loops during testing
    while current_url and step_count < 10:
        print(f"--- STEP {step_count + 1} processing {current_url} ---")
        
        # 1. Get the Hidden Question
        decoded_text = await fetch_and_decode_page(current_url)
        
        # 2. Parse it with LLM
        task_data = analyze_task(decoded_text)
        if not task_data:
            print("Failed to parse task.")
            break
            
        print(f"Task Found: {task_data}")
        
        # 3. Handle Files (if any)
        file_summary = "No files."
        if task_data.get("file_url"):
            # Handle relative URLs
            f_url = task_data["file_url"]
            if not f_url.startswith("http"):
                # Construct absolute URL based on current_url logic if needed
                # For now assume mostly absolute or handle simple join
                base_url = "/".join(current_url.split("/")[:3])
                f_url = base_url + f_url
            
            print(f"Downloading file: {f_url}")
            file_summary = parse_file_content(f_url)

        # 4. Solve
        answer = solve_question(task_data["question"], file_summary)
        print(f"Calculated Answer: {answer}")
        
        # 5. Submit
        submit_payload = {
            "email": STUDENT_EMAIL,
            "secret": STUDENT_SECRET,
            "url": current_url,
            "answer": answer
        }
        
        submit_url = task_data["submit_url"]
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(submit_url, json=submit_payload, timeout=30)
                result = resp.json()
                print(f"Submission Result: {result}")
                
                # 6. Check for next URL
                if result.get("correct") and result.get("url"):
                    current_url = result["url"]
                    step_count += 1
                else:
                    print("Quiz finished or answer incorrect.")
                    break
        except Exception as e:
            print(f"Submission failed: {e}")
            break


@app.post("/")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """
    The API Endpoint that receives the request.
    """
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    # Security Check
    if data.get("secret") != STUDENT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid Secret")
        
    quiz_url = data.get("url")
    
    # Start the "Brain" in the background so we can return 200 OK immediately
    background_tasks.add_task(run_quiz_process, quiz_url)
    
    return {"message": "Quiz processing started", "status": "ok"}

@app.get("/")
def health_check():
    return {"status": "active", "student": STUDENT_EMAIL}
