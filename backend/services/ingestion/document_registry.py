import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DocumentRegistry:
    @staticmethod
    def get_registry_path() -> Path:
        from backend.config import get_settings
        settings = get_settings()
        registry_path = settings.upload_path / "registry.json"
        return registry_path

    @classmethod
    def load(cls) -> Dict[str, Any]:
        path = cls.get_registry_path()
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def save(cls, data: Dict[str, Any]):
        path = cls.get_registry_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving registry: {e}")

    @classmethod
    def add_or_update(cls, filename: str, status: str, document_type: str = None, file_size: int = None, page_count: int = None, chunk_count: int = None, error: str = None):
        data = cls.load()
        if filename not in data:
            data[filename] = {
                "filename": filename,
                "document_type": document_type or filename.split(".")[-1].upper(),
                "status": status,
                "file_size": file_size or 0,
                "page_count": page_count or 0,
                "chunk_count": chunk_count or 0,
                "error": error
            }
        else:
            if status is not None:
                data[filename]["status"] = status
            if document_type is not None:
                data[filename]["document_type"] = document_type
            if file_size is not None:
                data[filename]["file_size"] = file_size
            if page_count is not None:
                data[filename]["page_count"] = page_count
            if chunk_count is not None:
                data[filename]["chunk_count"] = chunk_count
            if error is not None:
                data[filename]["error"] = error
        cls.save(data)

    @classmethod
    def delete(cls, filename: str):
        data = cls.load()
        if filename in data:
            del data[filename]
            cls.save(data)

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        from backend.database.vector_store import VectorStore
        try:
            chroma_docs = VectorStore.list_documents()
        except Exception:
            chroma_docs = []
            
        data = cls.load()
        
        updated = False
        for doc in chroma_docs:
            if doc not in data:
                from backend.config import get_settings
                settings = get_settings()
                filepath = settings.upload_path / doc
                size = filepath.stat().st_size if filepath.exists() else 0
                ext = filepath.suffix.lower().replace(".", "").upper()
                data[doc] = {
                    "filename": doc,
                    "document_type": ext,
                    "status": "Indexed",
                    "file_size": size,
                    "page_count": 0,
                    "chunk_count": 0
                }
                updated = True
        
        # Conversely, clean up entries in data that are not in uploads folder and not in chroma (e.g. deleted files)
        from backend.config import get_settings
        settings = get_settings()
        to_delete = []
        for doc in list(data.keys()):
            filepath = settings.upload_path / doc
            # If the file is not on disk and not in chromaDB, remove it from registry
            if not filepath.exists() and doc not in chroma_docs:
                to_delete.append(doc)
                
        for doc in to_delete:
            del data[doc]
            updated = True
            
        if updated:
            cls.save(data)
            
        return list(data.values())
