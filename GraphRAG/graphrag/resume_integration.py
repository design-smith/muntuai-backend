from datetime import datetime
from typing import Dict, List, Any
from .db.graph_db import Neo4jWrapper
from .db.vector_db import QdrantWrapper
from .embeddings.embedding_service import get_embedding

class ResumeGraphIntegrator:
    def __init__(self):
        self.graph_db = Neo4jWrapper()
        self.vector_db = QdrantWrapper()

    def integrate_resume(self, user_id: str, resume_data: Dict[str, Any]):
        """
        Integrate resume data into the graph database.
        """
        # 1. Verify user exists
        if not self.graph_db.node_exists("User", {"id": user_id}):
            raise ValueError(f"User {user_id} not found in graph database")

        # 2. Process work experience
        for exp in resume_data.get("work_experience", []):
            # Create or update Organization node
            org_id = f"org_{exp['company'].lower().replace(' ', '_')}"
            self.graph_db.merge_node("Organization", {
                "id": org_id,
                "name": exp["company"],
                "type": "company",
                "created_at": datetime.now()
            })

            # Create or update WORKED_AT relationship
            self.graph_db.merge_relationship(
                "User", "Organization",
                "WORKED_AT",
                {"id": user_id},
                {"id": org_id},
                {
                    "title": exp["title"],
                    "start_date": exp["start"],
                    "end_date": exp["end"],
                    "location": exp.get("location", ""),
                    "skills_used": exp.get("skills_used", [])
                }
            )

        # 3. Process education
        for edu in resume_data.get("education", []):
            # Create or update Organization node for educational institution
            school_id = f"edu_{edu['school'].lower().replace(' ', '_')}"
            self.graph_db.merge_node("Organization", {
                "id": school_id,
                "name": edu["school"],
                "type": "educational",
                "created_at": datetime.now()
            })

            # Create or update LEARNT_AT relationship
            self.graph_db.merge_relationship(
                "User", "Organization",
                "LEARNT_AT",
                {"id": user_id},
                {"id": school_id},
                {
                    "degree": edu["degree"],
                    "start_date": edu["start"],
                    "end_date": edu["end"],
                    "location": edu.get("location", ""),
                    "description": edu.get("description", "")
                }
            )

        # 4. Process skills
        for skill in resume_data.get("skills", []):
            # Create or update skill node
            skill_id = f"skill_{skill.lower().replace(' ', '_')}"
            self.graph_db.merge_node("Skill", {
                "id": skill_id,
                "name": skill,
                "created_at": datetime.now()
            })

            # Create or update HAS_SKILL relationship
            self.graph_db.merge_relationship(
                "User", "Skill",
                "HAS_SKILL",
                {"id": user_id},
                {"id": skill_id},
                {
                    "proficiency": "intermediate",  # Could be extracted from resume
                    "years_experience": 0  # Could be calculated from work experience
                }
            )

        # 5. Process certifications
        for cert in resume_data.get("certifications", []):
            # Create or update certification node
            cert_id = f"cert_{cert.lower().replace(' ', '_')}"
            self.graph_db.merge_node("Certification", {
                "id": cert_id,
                "name": cert,
                "created_at": datetime.now()
            })

            # Create or update HAS_CERTIFICATION relationship
            self.graph_db.merge_relationship(
                "User", "Certification",
                "HAS_CERTIFICATION",
                {"id": user_id},
                {"id": cert_id}
            )

        # 6. Process languages
        for lang in resume_data.get("languages", []):
            # Create or update language node
            lang_id = f"lang_{lang.lower().replace(' ', '_')}"
            self.graph_db.merge_node("Language", {
                "id": lang_id,
                "name": lang,
                "created_at": datetime.now()
            })

            # Create or update SPEAKS relationship
            self.graph_db.merge_relationship(
                "User", "Language",
                "SPEAKS",
                {"id": user_id},
                {"id": lang_id}
            )

        # 7. Create vector embeddings for searchable content
        # Create embedding for user profile
        profile_text = f"{resume_data.get('summary', '')} {' '.join(resume_data.get('skills', []))}"
        profile_embedding = get_embedding(profile_text)
        
        self.vector_db.upsert_embedding(
            "User",
            user_id,
            profile_embedding,
            {
                "id": user_id,
                "summary": resume_data.get("summary", ""),
                "skills": resume_data.get("skills", []),
                "created_at": datetime.now().isoformat()
            }
        )

    def close(self):
        """Close database connections"""
        self.graph_db.close() 