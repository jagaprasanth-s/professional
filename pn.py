import sqlite3
import os
import json
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "skill_rag.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        framework TEXT DEFAULT 'General Occupational Standard',
        file_size INTEGER DEFAULT 0,
        total_chunks INTEGER DEFAULT 0,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Chunks table with classification metadata
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL,
        skill_name TEXT NOT NULL,
        category TEXT NOT NULL,
        skill_type TEXT DEFAULT 'Technical Competency',
        content TEXT NOT NULL,
        definition TEXT,
        related_skills TEXT,
        differences TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
    );
    """)
    
    # Query history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS query_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL,
        skill_identified TEXT,
        answer TEXT,
        retrieved_chunk_ids TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_skill ON chunks(skill_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_category ON chunks(category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(document_id);")
    
    conn.commit()
    conn.close()

def insert_document(filename: str, framework: str, file_size: int = 0) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO documents (filename, framework, file_size) VALUES (?, ?, ?)",
        (filename, framework, file_size)
    )
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return doc_id

def insert_chunks(document_id: int, chunks_data: List[Dict[str, Any]]):
    conn = get_connection()
    cursor = conn.cursor()
    for c in chunks_data:
        related_skills_str = json.dumps(c.get("related_skills", [])) if isinstance(c.get("related_skills"), list) else str(c.get("related_skills", ""))
        differences_str = json.dumps(c.get("differences", {})) if isinstance(c.get("differences"), dict) else str(c.get("differences", ""))
        
        cursor.execute(
            """
            INSERT INTO chunks (
                document_id, chunk_index, skill_name, category, skill_type,
                content, definition, related_skills, differences
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                c.get("chunk_index", 0),
                c.get("skill_name", "Uncategorized Skill"),
                c.get("category", "General"),
                c.get("skill_type", "Technical Competency"),
                c.get("content", ""),
                c.get("definition", ""),
                related_skills_str,
                differences_str
            )
        )
    
    cursor.execute(
        "UPDATE documents SET total_chunks = (SELECT COUNT(*) FROM chunks WHERE document_id = ?) WHERE id = ?",
        (document_id, document_id)
    )
    conn.commit()
    conn.close()

def get_all_documents() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.filename, d.framework, d.file_size, d.total_chunks, d.uploaded_at,
               COUNT(c.id) as chunk_count
        FROM documents d
        LEFT JOIN chunks c ON d.id = c.document_id
        GROUP BY d.id
        ORDER BY d.uploaded_at DESC
    """)
    rows = cursor.fetchall()
    docs = [dict(row) for row in rows]
    conn.close()
    return docs

def delete_document(doc_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def get_all_chunks(limit: int = 100, offset: int = 0, category: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT c.*, d.filename as document_filename, d.framework as document_framework
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
    """
    params = []
    if category:
        query += " WHERE c.category = ?"
        params.append(category)
    query += " ORDER BY c.id ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    chunks = []
    for r in rows:
        item = dict(r)
        try:
            item["related_skills"] = json.loads(item["related_skills"])
        except Exception:
            pass
        try:
            item["differences"] = json.loads(item["differences"])
        except Exception:
            pass
        chunks.append(item)
    conn.close()
    return chunks

def search_chunks_text(search_term: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    like_pattern = f"%{search_term}%"
    cursor.execute("""
        SELECT c.*, d.filename as document_filename, d.framework as document_framework
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.skill_name LIKE ? OR c.content LIKE ? OR c.category LIKE ? OR c.definition LIKE ?
        ORDER BY 
            CASE 
                WHEN LOWER(c.skill_name) = LOWER(?) THEN 1
                WHEN c.skill_name LIKE ? THEN 2
                ELSE 3
            END,
            c.id ASC
    """, (like_pattern, like_pattern, like_pattern, like_pattern, search_term, like_pattern))
    rows = cursor.fetchall()
    results = []
    for r in rows:
        item = dict(r)
        try:
            item["related_skills"] = json.loads(item["related_skills"])
        except Exception:
            pass
        try:
            item["differences"] = json.loads(item["differences"])
        except Exception:
            pass
        results.append(item)
    conn.close()
    return results

def get_all_skills_taxonomy() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT c.skill_name, c.category, c.skill_type, d.framework, COUNT(c.id) as chunk_instances
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        GROUP BY c.skill_name, c.category, c.skill_type, d.framework
        ORDER BY c.category ASC, c.skill_name ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM documents")
    total_docs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM chunks")
    total_chunks = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT category) FROM chunks")
    total_categories = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT skill_name) FROM chunks")
    total_skills = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT category, COUNT(*) as count 
        FROM chunks 
        GROUP BY category 
        ORDER BY count DESC
    """)
    categories = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {
        "total_documents": total_docs,
        "total_chunks": total_chunks,
        "total_categories": total_categories,
        "total_skills": total_skills,
        "category_breakdown": categories
    }

def log_query(query: str, skill_identified: str, answer: str, chunk_ids: List[int]):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO query_logs (query, skill_identified, answer, retrieved_chunk_ids) VALUES (?, ?, ?, ?)",
        (query, skill_identified, answer, json.dumps(chunk_ids))
    )
    conn.commit()
    conn.close()

def get_query_logs(limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM query_logs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]