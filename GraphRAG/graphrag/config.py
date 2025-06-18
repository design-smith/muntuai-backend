from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    # Neo4j Configuration
    NEO4J_URI: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    NEO4J_USER: str = Field(default="neo4j", alias="NEO4J_USERNAME")
    NEO4J_PASSWORD: str = Field(default="password", alias="NEO4J_PASSWORD")
    
    # Qdrant Configuration
    QDRANT_URL: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    QDRANT_API_KEY: str = Field(default=None, alias="QDRANT_API_KEY")
    
    # Embedding Configuration
    EMBEDDING_MODEL: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")

    # Extra fields for compatibility with environment
    DEEPSEEK_API_KEY: str = Field(default=None, alias="DEEPSEEK_API_KEY")

    CORS_ORIGINS: List[str] = ["*"]  # Allow all origins by default for dev

    model_config = {
        "env_file": ".env",
        "extra": "allow"
    }

@lru_cache()
def get_settings() -> Settings:
    return Settings()

if __name__ == "__main__":
    print("[DEBUG] config.py __main__ block started.")
    import os
    print("\n--- Debug: ALL Environment Variables ---")
    for k, v in os.environ.items():
        print(f"{k} = {v}")
    print("--- End Debug ---\n")
    print("\n--- Debug: Settings Loaded Values ---")
    try:
        settings = get_settings()
        print(settings)
    except Exception as e:
        print("Settings load error:", e)
    print("--- End Debug ---\n")
    print("[DEBUG] config.py __main__ block finished.") 