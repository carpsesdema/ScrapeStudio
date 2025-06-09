# scraper/rag_models.py
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, HttpUrl, Field
import uuid


class FetchedItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_url: HttpUrl
    content: Optional[str] = None
    content_bytes: Optional[bytes] = None
    content_type_detected: Optional[str] = None
    source_type: str
    query_used: str
    title: Optional[str] = None
    encoding: Optional[str] = None


class ExtractedLinkInfo(BaseModel):
    url: HttpUrl
    text: Optional[str] = None
    rel: Optional[str] = None


class ParsedItem(BaseModel):
    id: str
    fetched_item_id: str
    source_url: HttpUrl
    source_type: str
    query_used: str
    title: Optional[str] = None
    main_text_content: Optional[str] = None
    extracted_structured_blocks: List[Dict[str, Any]] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    extracted_links: List[ExtractedLinkInfo] = Field(default_factory=list)
    parser_metadata: Dict[str, Any] = Field(default_factory=dict)


class StructuredDataItem(BaseModel):
    """The final, clean output model focused on structured data."""
    id: str
    source_url: HttpUrl
    source_type: str
    query_used: str
    title: Optional[str] = None

    # The primary payload: your clean, structured data!
    structured_data: Dict[str, Any] = Field(default_factory=dict)

    # Optional unstructured text and metadata
    unstructured_text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)