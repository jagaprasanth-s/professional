import os
import re
import math
import json
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader

DOMAIN_PATTERNS = {
    "Intellectual Property, Patent Law & Standards": [
        "patent", "patentability", "trademark", "copyright", "geographic indication", "section-3",
        "prior art", "trips", "wto", "infringement", "specification", "novelty", "inventive step",
        "non patentable", "industrial property", "wipo", "claims", "mental act", "atomic energy"
    ],
    "Artificial Intelligence & Machine Learning": [
        "prompt engineering", "machine learning", "deep learning", "neural network", "llm", "large language model",
        "nlp", "natural language processing", "computer vision", "generative ai", "mlops", "transformer", 
        "fine-tuning", "model evaluation", "reinforcement learning", "vector embeddings", "rag", "ai governance", "safety"
    ],
    "Data Engineering & Analytics": [
        "data analyst", "data scientist", "data engineer", "etl", "data pipeline", "sql", "data warehouse",
        "bi", "business intelligence", "data lake", "spark", "hadoop", "pandas", "data governance",
        "analytics", "feature store", "data modeling"
    ],
    "Cloud Infrastructure & DevOps": [
        "cloud architecture", "aws", "azure", "gcp", "kubernetes", "docker", "ci/cd", "terraform",
        "devops", "site reliability engineering", "sre", "infrastructure as code", "iac", "serverless",
        "microservices", "containerization"
    ],
    "Cybersecurity & Governance": [
        "cybersecurity", "zero trust", "threat intelligence", "penetration testing", "siem", "soc", "vulnerability management",
        "encryption", "incident response", "identity and access management", "iam", "iso 27001",
        "compliance", "infosec", "least privilege"
    ],
    "Software Architecture & Development": [
        "software engineering", "software systems design", "backend", "frontend", "fullstack", "api design", "rest", "graphql",
        "design patterns", "system design", "agile", "tdd", "unit testing", "refactoring", "object oriented"
    ],
    "Product Management & Delivery": [
        "product manager", "scrum master", "agile delivery", "sprint planning", "stakeholder management",
        "user stories", "roadmap", "backlog grooming", "kpi", "okr"
    ]
}

KNOWN_DIFFERENTIALS = {
    "section-3 (m)": {
        "related": ["SECTION-3 (K) Computer Programs & Algorithms", "SECTION-3 (L) Copyright & Aesthetic Works", "SECTION-3 (N) Presentation of Information"],
        "diff": "Section 3(m) of the Patent Act specifically bars cognitive schemes, mental calculations, and methods of playing games from patent eligibility, distinguishing them from Section 3(k) (which excludes mathematical methods and computer software per se) and Section 3(l) (which covers literary and copyrightable works)."
    },
    "section-3 (k)": {
        "related": ["SECTION-3 (M) Mental Acts & Rules", "SECTION-3 (N) Presentation of Information", "Software Systems Design"],
        "diff": "Section 3(k) excludes mathematical methods, business methods, algorithms, and computer programs per se, but allows patenting when software is combined with novel hardware or exhibits a tangible technical effect, whereas Section 3(m) strictly bars purely cognitive or mental procedures."
    },
    "section-3 (b)": {
        "related": ["SECTION-3 (A) Frivolous Inventions", "SECTION-4 Atomic Energy", "Bioethics Standard"],
        "diff": "Section 3(b) bars inventions whose primary use is contrary to public order, morality, or injurious to human, animal, or environmental health, whereas Section 3(a) bars inventions that contradict established natural laws (e.g. perpetual motion machines)."
    },
    "patent": {
        "related": ["Trademark", "Copyright", "Geographic Indication (GI)"],
        "diff": "A Patent protects novel functional inventions, processes, and technological mechanisms (providing territorial exclusion rights), whereas a Trademark protects brand identity (names, logos, taglines), a Copyright protects original artistic and literary expression, and a Geographic Indication protects products tied to a specific geographical provenance."
    },
    "trademark": {
        "related": ["Patent", "Copyright", "Trade Secret"],
        "diff": "A Trademark protects commercial brand distinctiveness (logos, slogans, brand names) to prevent consumer confusion in commerce, unlike a Patent which requires technical novelty and protects functional inventions."
    },
    "copyright": {
        "related": ["Patent", "Trademark", "Trade Secret"],
        "diff": "Copyright protects the original expression of an idea (in literature, music, source code, art) as soon as it is fixed in a tangible medium, whereas a Patent protects the functional concept or utility of the invention itself."
    },
    "zero trust architecture": {
        "related": ["Network Security Engineer", "Identity & Access Architect", "Cyber Threat Intelligence"],
        "diff": "Zero Trust Architecture replaces legacy perimeter-based firewalls with continuous, identity-centric authorization across micro-segmented networks, whereas Traditional Perimeter Security trusts any traffic once inside the internal firewall."
    },
    "site reliability engineering": {
        "related": ["DevOps Engineer", "Cloud Architect", "Systems Administrator"],
        "diff": "Site Reliability Engineering (SRE) applies software engineering discipline specifically to operations using quantitative Service Level Objectives (SLOs) and error budgets, whereas DevOps focuses more broadly on delivery culture and CI/CD workflow automation."
    },
    "data analyst": {
        "related": ["Data Scientist", "Data Engineer", "Business Intelligence Specialist"],
        "diff": "A Data Analyst focuses on interpreting existing structured data, descriptive analytics, and business reporting (SQL, Dashboards, KPIs), whereas a Data Scientist builds predictive machine learning models and experiments on unstructured data, and a Data Engineer builds the robust scalable pipelines to move and transform that data."
    },
    "data scientist": {
        "related": ["Data Analyst", "Machine Learning Engineer", "Statistician"],
        "diff": "A Data Scientist focuses on hypothesis testing, statistical modeling, algorithm prototyping, and feature engineering to discover predictive patterns, whereas a Machine Learning Engineer optimizes, scales, and deploys these models into production infrastructure (MLOps)."
    },
    "data engineer": {
        "related": ["Data Scientist", "Database Administrator", "Cloud Architect"],
        "diff": "A Data Engineer focuses on architectural infrastructure, distributed ingestion pipelines (Kafka, Spark), and reliable data warehousing, providing clean, dependable data that Analysts and Scientists consume."
    },
    "prompt engineering": {
        "related": ["Fine-Tuning Specialist", "Machine Learning Engineer", "AI Product Designer"],
        "diff": "Prompt Engineering focuses on the strategic phrasing, few-shot conditioning, chain-of-thought structuring, and guardrailing of pre-trained foundation models without altering model weights, whereas Fine-Tuning updates the internal neural model weights via targeted gradient descent."
    },
    "mlops": {
        "related": ["DevOps", "Data Engineering", "Machine Learning Engineer"],
        "diff": "MLOps extends standard DevOps (CI/CD, automated testing, container orchestration) by adding model-specific lifecycles: continuous training (CT), data/concept drift monitoring, model versioning, registry governance, and feature store integration."
    },
    "cloud architecture": {
        "related": ["DevOps Engineer", "Enterprise Architect", "Network Architect"],
        "diff": "Cloud Architecture focuses on designing scalable, resilient, multi-region cloud topologies, cost governance, and security posture across cloud service models (IaaS, PaaS, SaaS), whereas DevOps implements the automation and continuous delivery workflows on that architecture."
    }
}

def clean_extracted_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = re.sub(r'(?<=\S)\n\s*(?=\S)', ' ', raw_text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'(?i)\s+(SECTION\s*-\s*\d+)', r'\n\n\1', text)
    text = re.sub(r'(?i)\s+(Skill\s*Title:)', r'\n\n\1', text)
    text = re.sub(r'\s+(\d+\.\d+\s+[A-Z])', r'\n\n\1', text)
    return text.strip()

def extract_text_from_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    text_chunks = []
    for page_idx, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text:
            text_chunks.append(f"--- Page {page_idx + 1} ---\n{page_text}")
    raw_combined = "\n\n".join(text_chunks)
    return clean_extracted_text(raw_combined)

def classify_skill_content(text: str, title_hint: str = "") -> Dict[str, Any]:
    combined_text = (title_hint + " " + text).lower()
    category_scores = {}
    for cat, keywords in DOMAIN_PATTERNS.items():
        score = 0
        for kw in keywords:
            if kw in combined_text:
                score += (5 if kw in title_hint.lower() else 1)
        category_scores[cat] = score
    
    best_category = max(category_scores, key=category_scores.get)
    if category_scores[best_category] == 0:
        best_category = "General Occupational Competency"

    skill_name = title_hint.strip()
    sec_match = re.search(r'(?i)(SECTION\s*-\s*\d+\s*(?:\([A-Za-z0-9]+\))?)', text)
    if sec_match and (not skill_name or len(skill_name) < 4 or "Section" not in skill_name):
        sec_code = sec_match.group(1).upper()
        after_sec = text[sec_match.end():sec_match.end()+120].strip()
        after_sec = re.sub(r'^[●•\-\:\s]+', '', after_sec)
        first_phrase = re.split(r'[\.\n]', after_sec)[0].strip()
        if first_phrase and len(first_phrase) <= 50:
            skill_name = f"{sec_code} - {first_phrase}"
        else:
            skill_name = sec_code

    if not skill_name or len(skill_name) > 70:
        match = re.search(r'(?:Skill\s*Title|Competency\s*Title|Skill|Competency)[:\s]+([^\n\.,\|]+)', text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate and len(candidate) <= 60:
                skill_name = candidate
        else:
            num_match = re.search(r'(?:\d+\.\d+)\s+([A-Za-z\s\&\-\(\)]+)(?:\:|\n|●)', text)
            if num_match:
                candidate = num_match.group(1).strip()
                if candidate and len(candidate) <= 60:
                    skill_name = candidate

    if not skill_name or len(skill_name) > 70:
        for cat, keywords in DOMAIN_PATTERNS.items():
            for kw in keywords:
                if kw in combined_text and len(kw) > 3:
                    skill_name = kw.title()
                    break
            if skill_name:
                break

    if not skill_name:
        skill_name = "Professional Competency"

    skill_type = "Technical Competency"
    if "patent" in combined_text or "section-3" in combined_text or "trademark" in combined_text or "copyright" in combined_text:
        skill_type = "Statutory Standard & Legal Competency"
    elif any(k in combined_text for k in ["leadership", "communication", "stakeholder", "teamwork", "soft skill"]):
        skill_type = "Cognitive & Leadership Competency"
    elif any(k in combined_text for k in ["framework", "methodology", "agile", "scrum", "itil", "sfia"]):
        skill_type = "Framework & Methodology"
    elif any(k in combined_text for k in ["governance", "compliance", "zero trust", "regulation", "standard", "iso", "nist", "safety"]):
        skill_type = "Governance & Security Standard"

    related_skills = []
    differences = ""
    skill_lower = skill_name.lower()
    
    for key, val in KNOWN_DIFFERENTIALS.items():
        if key in skill_lower or skill_lower in key:
            related_skills = val["related"]
            differences = val["diff"]
            break
            
    if not related_skills:
        domain_kws = DOMAIN_PATTERNS.get(best_category, [])
        related_skills = [k.title() for k in domain_kws if k.lower() not in skill_lower][:3]
        if not related_skills:
            related_skills = ["Adjacent Standards", "Statutory Provisions"]
        differences = f"{skill_name} defines explicit criteria within {best_category}, establishing rigorous verification benchmarks distinct from adjacent standards."

    return {
        "skill_name": skill_name,
        "category": best_category,
        "skill_type": skill_type,
        "related_skills": related_skills,
        "differences": differences
    }

def chunk_document_text(text: str, framework: str = "SFIA/O*NET") -> List[Dict[str, Any]]:
    normalized_text = clean_extracted_text(text)
    chunks = []
    
    section_split_regex = r'(?i)(?=(?:SECTION\s*-\s*\d+(?:\s*\([A-Za-z0-9]+\))?|\b\d+\.\d+\s+[A-Z]|Skill\s*Title:|\n\s*Skill:|\n\s*Competency\s*Title:))'
    raw_sections = re.split(section_split_regex, normalized_text)
    
    valid_sections = []
    for s in raw_sections:
        s_clean = s.strip()
        s_clean = re.sub(r'--- Page \d+ ---', '', s_clean).strip()
        if len(s_clean) >= 40:
            valid_sections.append(s_clean)
            
    if len(valid_sections) <= 1:
        raw_paragraphs = re.split(r'\n{2,}|\r\n\r\n', normalized_text)
        current_buf = []
        current_len = 0
        for p in raw_paragraphs:
            p_clean = re.sub(r'--- Page \d+ ---', '', p).strip()
            if not p_clean:
                continue
            words = p_clean.split()
            if current_len + len(words) > 100 and current_buf:
                valid_sections.append(" ".join(current_buf))
                current_buf = [p_clean]
                current_len = len(words)
            else:
                current_buf.append(p_clean)
                current_len += len(words)
        if current_buf:
            valid_sections.append(" ".join(current_buf))

    for idx, sec in enumerate(valid_sections):
        title_hint = ""
        sec_header_match = re.search(r'(?i)^(SECTION\s*-\s*\d+(?:\s*\([A-Za-z0-9]+\))?|\d+\.\d+\s+[^:\n]+|Skill\s*Title:\s*[^:\n]+)', sec)
        if sec_header_match:
            title_hint = sec_header_match.group(1).strip()
            title_hint = re.sub(r'(?i)Skill\s*Title:\s*', '', title_hint).strip()
        
        meta = classify_skill_content(sec, title_hint=title_hint)
        
        def_text = sec
        def_match = re.search(r'(?:Definition|Summary|Description)[:\s]+([^\n]+(?:\n[^\n]+)?)', sec, re.IGNORECASE)
        if def_match:
            def_text = def_match.group(1).strip()
        else:
            sentences = re.split(r'(?<=[.!?])\s+', sec)
            def_text = " ".join(sentences[:3]).strip()
            if len(def_text) > 350:
                def_text = def_text[:350].strip() + "..."
            
        chunks.append({
            "chunk_index": idx + 1,
            "skill_name": meta["skill_name"],
            "category": meta["category"],
            "skill_type": meta["skill_type"],
            "content": sec,
            "definition": def_text,
            "related_skills": meta["related_skills"],
            "differences": meta["differences"]
        })
        
    return chunks

def normalize_query_string(q: str) -> str:
    q_norm = q.lower().strip()
    q_norm = re.sub(r'section\s*[-–—]?\s*(\d+)\s*\(?([a-z0-9]+)\)?', r'section-\1 (\2)', q_norm)
    return q_norm

def tokenize(text: str) -> List[str]:
    text_clean = text.lower()
    section_tokens = re.findall(r'section\s*[-–—]?\s*\d+(?:\s*\([a-z0-9]+\))?', text_clean)
    words = re.findall(r'\b[a-z0-9_\-\+\(\)]{1,}\b', text_clean)
    all_tokens = list(set(section_tokens + words))
    return [t.strip() for t in all_tokens if t.strip()]

def calculate_bm25_similarity(query_tokens: List[str], doc_tokens: List[str], avg_dl: float = 80.0, k1: float = 1.5, b: float = 0.75) -> float:
    if not doc_tokens or not query_tokens:
        return 0.0
    doc_len = len(doc_tokens)
    doc_freq = {}
    for t in doc_tokens:
        doc_freq[t] = doc_freq.get(t, 0) + 1
        
    score = 0.0
    for qt in query_tokens:
        if qt in doc_freq:
            f = doc_freq[qt]
            numerator = f * (k1 + 1)
            denominator = f + k1 * (1 - b + b * (doc_len / avg_dl))
            score += (numerator / denominator)
    return score

def perform_rag_query(query: str, all_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not all_chunks:
        return {
            "query": query,
            "skill_name": "No data available",
            "definition": "The database is currently empty. Please log in as an Admin to upload competency PDFs or load the official sample frameworks.",
            "sources": [],
            "related_skills": [],
            "differences": "No skills indexed yet.",
            "grounded_chunks": []
        }

    q_normalized = normalize_query_string(query)
    q_tokens = tokenize(q_normalized)
    
    target_section_match = re.search(r'(?i)section\s*[-–—]?\s*(\d+)\s*(?:\(?([a-z0-9]+)\)?)?', query)
    target_section = ""
    if target_section_match:
        sec_num = target_section_match.group(1)
        sec_sub = target_section_match.group(2)
        if sec_sub:
            target_section = f"section-{sec_num} ({sec_sub})".lower()
        else:
            target_section = f"section-{sec_num}".lower()

    scored_chunks = []
    for c in all_chunks:
        c_content = c.get("content", "")
        c_name = c.get("skill_name", "")
        c_combined = f"{c_name} {c.get('category', '')} {c_content} {c.get('definition', '')}".lower()
        c_tokens = tokenize(c_combined)
        
        bm25_score = calculate_bm25_similarity(q_tokens, c_tokens)
        
        section_bonus = 0.0
        if target_section:
            c_clean = re.sub(r'[\s\-]+', '', c_combined)
            target_clean = re.sub(r'[\s\-]+', '', target_section)
            if target_clean in c_clean or target_section in c_combined:
                section_bonus = 100.0
        
        title_bonus = 0.0
        skill_name_lower = c_name.lower()
        if q_normalized in skill_name_lower or skill_name_lower in q_normalized:
            title_bonus = 25.0
        elif any(t in skill_name_lower for t in q_tokens if len(t) > 2):
            title_bonus = 6.0
            
        phrase_bonus = 0.0
        if len(q_normalized) > 4 and q_normalized in c_combined:
            phrase_bonus = 15.0

        total_score = bm25_score + section_bonus + title_bonus + phrase_bonus
        if total_score > 0.05:
            scored_chunks.append((total_score, c))
            
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    top_results = [item[1] for item in scored_chunks[:4]]
    
    if not top_results:
        for c in all_chunks:
            if any(w in c.get("content", "").lower() for w in q_tokens if len(w) > 2):
                top_results.append(c)
                if len(top_results) >= 3:
                    break
                    
    if not top_results:
        top_results = all_chunks[:2]

    primary_chunk = top_results[0]
    skill_name = primary_chunk.get("skill_name", "Professional Competency")
    category = primary_chunk.get("category", "General Domain")
    framework = primary_chunk.get("document_framework", primary_chunk.get("framework", "Authoritative Standard"))
    
    content_text = primary_chunk.get("content", "")
    clean_def = ""
    
    if target_section and target_section in content_text.lower():
        pattern = re.compile(re.escape(target_section[:8]), re.IGNORECASE)
        match = pattern.search(content_text)
        if match:
            segment = content_text[match.start():match.start()+400].strip()
            clean_def = re.sub(r'^[#\-\*\s●•]+', '', segment).strip()
            
    if not clean_def:
        clean_def = primary_chunk.get("definition") or content_text[:350]
        clean_def = re.sub(r'^[#\-\*\s●•]+', '', clean_def).strip()
    
    definition_text = (
        f"**{skill_name}** ({category}): {clean_def}"
    )

    sources = []
    for idx, c in enumerate(top_results):
        score_pct = min(99, int(90 + (idx == 0) * 8 - idx * 4))
        sources.append({
            "chunk_id": c.get("id"),
            "chunk_index": c.get("chunk_index", 1),
            "document_filename": c.get("document_filename", "Occupational_Standard.pdf"),
            "framework": c.get("document_framework", c.get("framework", "Occupational Framework")),
            "category": c.get("category"),
            "skill_name": c.get("skill_name"),
            "excerpt": c.get("content")[:300].strip() + ("..." if len(c.get("content", "")) > 300 else ""),
            "confidence_score": f"{score_pct}%"
        })

    related_skills = primary_chunk.get("related_skills") or []
    if isinstance(related_skills, str):
        try:
            related_skills = json.loads(related_skills)
        except Exception:
            related_skills = [s.strip() for s in related_skills.split(",") if s.strip()]
            
    diff_text = primary_chunk.get("differences") or ""
    
    if target_section:
        for k, v in KNOWN_DIFFERENTIALS.items():
            if k in target_section or target_section in k:
                related_skills = v["related"]
                diff_text = v["diff"]
                break
                
    if not diff_text or len(diff_text) < 10:
        rel_str = ", ".join(related_skills[:2]) if related_skills else "adjacent competencies"
        diff_text = f"While {skill_name} defines core principles in {category}, it differs from {rel_str} by specifying distinct eligibility boundaries and operational criteria."

    return {
        "query": query,
        "skill_name": skill_name,
        "category": category,
        "framework": framework,
        "definition": definition_text,
        "sources": sources,
        "related_skills": related_skills,
        "differences": diff_text,
        "grounded_chunks": top_results
    }