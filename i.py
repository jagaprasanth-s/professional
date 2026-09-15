import os
import shutil
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from . import db
from . import pipeline
from . import seed_data

db.init_db()

app = FastAPI(title="Professional Skill Definition RAG", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

class LoginRequest(BaseModel):
    role: str
    email: Optional[str] = "admin@skillrag.io"
    password: Optional[str] = "admin123"

class QueryRequest(BaseModel):
    query: str
    category: Optional[str] = None
    framework: Optional[str] = None

@app.post("/api/auth/login")
def login(req: LoginRequest):
    role = req.role.lower()
    if role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'user'.")
    
    user_name = "Admin Curator" if role == "admin" else "Professional User"
    return {
        "success": True,
        "token": f"mock-jwt-token-{role}-session",
        "user": {
            "name": user_name,
            "email": req.email or (f"{role}@skillrag.io"),
            "role": role
        }
    }

@app.get("/api/admin/stats")
def get_stats():
    return db.get_stats()

@app.get("/api/admin/documents")
def list_documents():
    return db.get_all_documents()

@app.delete("/api/admin/documents/{doc_id}")
def delete_doc(doc_id: int):
    success = db.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"success": True, "message": "Document and all classified chunks deleted permanently."}

@app.get("/api/admin/chunks")
def list_chunks(limit: int = 100, offset: int = 0, category: Optional[str] = None, search: Optional[str] = None):
    if search:
        return db.search_chunks_text(search)
    return db.get_all_chunks(limit=limit, offset=offset, category=category)

@app.post("/api/admin/seed")
def load_sample_frameworks():
    success, message = seed_data.load_seed_data()
    return {"success": success, "message": message, "stats": db.get_stats()}

@app.post("/api/admin/reprocess")
def reprocess_all_documents():
    docs = db.get_all_documents()
    total_reprocessed = 0
    total_new_chunks = 0
    for d in docs:
        filename = d['filename']
        upload_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(upload_path):
            if filename.lower().endswith(".pdf"):
                text = pipeline.extract_text_from_pdf(upload_path)
            else:
                with open(upload_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = pipeline.clean_extracted_text(f.read())
            chunks = pipeline.chunk_document_text(text, framework=d.get('framework', 'Occupational Standard'))
            if chunks:
                conn = db.get_connection()
                conn.execute("DELETE FROM chunks WHERE document_id = ?", (d['id'],))
                conn.commit()
                conn.close()
                db.insert_chunks(d['id'], chunks)
                total_reprocessed += 1
                total_new_chunks += len(chunks)
    return {
        "success": True,
        "message": f"Successfully reprocessed {total_reprocessed} documents into {total_new_chunks} refined chunks.",
        "stats": db.get_stats()
    }

@app.post("/api/admin/upload")
async def upload_document(
    file: Optional[UploadFile] = File(None),
    framework: str = Form("General Occupational Standard"),
    title: Optional[str] = Form(None),
    raw_text: Optional[str] = Form(None)
):
    extracted_text = ""
    filename = ""
    file_size = 0
    
    if file and file.filename:
        filename = file.filename
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        file_size = os.path.getsize(file_path)
        
        if filename.lower().endswith(".pdf"):
            try:
                extracted_text = pipeline.extract_text_from_pdf(file_path)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    extracted_text = pipeline.clean_extracted_text(f.read())
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
    elif raw_text:
        filename = (title.strip() if title else "Direct_Input_Competency") + ".txt"
        file_size = len(raw_text.encode("utf-8"))
        extracted_text = pipeline.clean_extracted_text(raw_text)
    else:
        raise HTTPException(status_code=400, detail="Either a file or raw_text must be provided.")

    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="The uploaded document contains no readable text.")

    chunks = pipeline.chunk_document_text(extracted_text, framework=framework)
    if not chunks:
        raise HTTPException(status_code=400, detail="Could not derive any valid chunks from the text.")

    doc_id = db.insert_document(filename=filename, framework=framework, file_size=file_size)
    db.insert_chunks(document_id=doc_id, chunks_data=chunks)

    return {
        "success": True,
        "message": f"Successfully parsed, classified, and stored {len(chunks)} chunks forever in the SQLite database.",
        "document_id": doc_id,
        "filename": filename,
        "framework": framework,
        "total_chunks": len(chunks),
        "chunks_preview": chunks[:3]
    }

@app.post("/api/user/query")
def query_skill(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    all_chunks = db.get_all_chunks(limit=500)
    rag_result = pipeline.perform_rag_query(req.query, all_chunks)
    
    chunk_ids = [s.get("chunk_id") for s in rag_result.get("sources", []) if s.get("chunk_id")]
    db.log_query(
        query=req.query,
        skill_identified=rag_result.get("skill_name", ""),
        answer=rag_result.get("definition", ""),
        chunk_ids=chunk_ids
    )
    
    return rag_result

@app.get("/api/user/skills")
def get_skills_taxonomy():
    return db.get_all_skills_taxonomy()

@app.get("/api/user/history")
def get_history(limit: int = 15):
    return db.get_query_logs(limit=limit)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)w