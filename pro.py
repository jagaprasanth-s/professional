import os
import sys
import uvicorn

if __name__ == "__main__":
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    print("=" * 65)
    print("   Professional Skill Definition RAG Prototype")
    print("   Authoritative Competency Engine (SFIA 8 & O*NET)")
    print("=" * 65)
    print(" Starting Fullstack Server on http://127.0.0.1:8000")
    print(" - Login Page: http://127.0.0.1:8000")
    print(" - Admin Dashboard & User RAG Assistant available")
    print(" - Persistent SQLite Database: data/skill_rag.db")
    print("=" * 65)
    
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)