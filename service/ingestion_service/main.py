from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from typing import Optional
import uvicorn
import os
from processing import process_and_load_to_db

app = FastAPI()

@app.post("/process/")
async def process_source(
    background_tasks: BackgroundTasks,
    source_type: str = Form(...),
    # The 'path' will now be a path accessible by the service
    path: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """
    Endpoint to process a new source (file path or uploaded file).
    - For sources already on disk (crawled), use 'path'.
    - For direct uploads, use 'file'.
    """
    if path and source_type in ["pdf", "youtube"]:
        # Process a file that's already on disk (e.g., from crawler)
        background_tasks.add_task(process_and_load_to_db, path, source_type)
        return {"status": "processing_started", "source_type": source_type, "path": path}
        
    elif file and source_type in ["pdf", "txt"]: # Assuming 'txt' can be handled like youtube transcripts
        temp_dir = "temp_files"
        os.makedirs(temp_dir, exist_ok=True)
        
        filename = file.filename if file.filename else "uploaded_file"
        file_location = os.path.join(temp_dir, filename)
        
        with open(file_location, "wb+") as file_object:
            file_object.write(await file.read())
        
        file_type_for_processing = "youtube" if source_type == "txt" else source_type
        background_tasks.add_task(process_and_load_to_db, file_location, file_type_for_processing)
        
        return {
            "status": "processing_started",
            "source_type": source_type,
            "filename": filename,
        }
    else:
        return {"error": "Invalid request. Provide a valid source_type and corresponding path or file."}, 400

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 