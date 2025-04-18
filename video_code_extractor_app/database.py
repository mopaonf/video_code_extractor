from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func, or_, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import re
import json

Base = declarative_base()

class CodeSnippet(Base):
    __tablename__ = 'code_snippets'

    id = Column(Integer, primary_key=True)
    timestamp = Column(String(20), nullable=False)
    language = Column(String(50), nullable=False)
    code = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)  # Add created_at column
    source_file = Column(String(255), nullable=True)  # Add source_file column
    
    def to_dict(self):
        """Convert snippet to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "language": self.language,
            "code": self.code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "source_file": self.source_file
        }
    
    @staticmethod
    def from_dict(data):
        """Create a snippet from dictionary data."""
        return CodeSnippet(
            timestamp=data.get("timestamp", "00:00:00"),
            language=data.get("language", "Unknown"),
            code=data.get("code", ""),
            source_file=data.get("source_file")
        )

# Database setup
engine = create_engine('sqlite:///code_snippets.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

def add_snippet(timestamp, language, code, source_file=None):
    """Add a new code snippet to the database."""
    snippet = CodeSnippet(
        timestamp=timestamp,
        language=language,
        code=code,
        source_file=source_file
    )
    session.add(snippet)
    session.commit()
    return snippet

def get_all_snippets():
    """Get all snippets from the database."""
    return session.query(CodeSnippet).order_by(CodeSnippet.timestamp).all()

def get_snippet_by_id(snippet_id):
    """Get a specific snippet by ID."""
    return session.query(CodeSnippet).filter(CodeSnippet.id == snippet_id).first()

def get_snippets_by_language(language):
    """Get all snippets for a specific language."""
    return session.query(CodeSnippet).filter(CodeSnippet.language == language).all()

def get_snippets_by_time_range(start_time, end_time):
    """Get snippets within a specific time range."""
    return session.query(CodeSnippet).filter(
        CodeSnippet.timestamp >= start_time,
        CodeSnippet.timestamp <= end_time
    ).all()

def get_snippets_containing(text):
    """Get snippets containing specific text."""
    search_pattern = f"%{text}%"
    return session.query(CodeSnippet).filter(CodeSnippet.code.like(search_pattern)).all()

def delete_snippet(snippet_id):
    """Delete a snippet by ID."""
    snippet = session.query(CodeSnippet).filter(CodeSnippet.id == snippet_id).first()
    if snippet:
        session.delete(snippet)
        session.commit()
        return True
    return False

def filter_snippets(language=None, start_time=None, end_time=None, content=None, remove_duplicates=False):
    """Filter snippets based on multiple criteria."""
    query = session.query(CodeSnippet)
    
    # Apply language filter
    if language:
        query = query.filter(CodeSnippet.language == language)
    
    # Apply time range filter
    if start_time:
        query = query.filter(CodeSnippet.timestamp >= start_time)
    if end_time:
        query = query.filter(CodeSnippet.timestamp <= end_time)
    
    # Apply content filter
    if content:
        query = query.filter(CodeSnippet.code.like(f"%{content}%"))
    
    # Get results
    results = query.order_by(CodeSnippet.timestamp).all()
    
    # Remove duplicates if required
    if remove_duplicates:
        unique_snippets = []
        code_hashes = set()
        for snippet in results:
            code_hash = hash(snippet.code)
            if code_hash not in code_hashes:
                unique_snippets.append(snippet)
                code_hashes.add(code_hash)
        return unique_snippets
    
    return results

def export_all_to_json(file_path):
    """Export all snippets to a JSON file."""
    snippets = get_all_snippets()
    data = [snippet.to_dict() for snippet in snippets]
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def import_from_json(file_path):
    """Import snippets from a JSON file."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    for item in data:
        snippet = CodeSnippet.from_dict(item)
        session.add(snippet)
    
    session.commit()

def clear_database():
    """Remove all snippets from the database."""
    session.query(CodeSnippet).delete()
    session.commit()

def get_statistics():
    """Get statistics about the database."""
    total_snippets = session.query(CodeSnippet).count()
    languages = session.query(CodeSnippet.language, func.count(CodeSnippet.id)).group_by(CodeSnippet.language).all()
    
    language_stats = {lang: count for lang, count in languages}
    
    return {
        "total_snippets": total_snippets,
        "languages": language_stats
    }

def search_snippets(query):
    """Search snippets by language or content."""
    return session.query(CodeSnippet).filter(
        or_(
            CodeSnippet.language.like(f"%{query}%"),
            CodeSnippet.code.like(f"%{query}%")
        )
    ).all()