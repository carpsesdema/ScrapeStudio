# rag_data_studio/core/models.py
"""
Core data models for the Data Extractor Studio application.
This is the single source of truth for project and rule structures.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ScrapingRule:
    """
    Defines a rule for extracting a piece of data.
    Supports nesting for structured data extraction (e.g., table rows).
    """
    id: str
    name: str
    selector: str
    description: Optional[str] = ""
    extraction_type: str = "text"  # 'text', 'attribute', 'html', 'structured_list'
    attribute_name: Optional[str] = None
    # For a 'structured_list', this is implicitly True.
    # For other types, it means "get all elements matching the selector as a simple list of values".
    is_list: bool = False
    data_type: str = "string" # E.g., 'string', 'number', 'list_of_strings', 'list_of_objects'
    required: bool = False
    # Crucial for nested data: a list of rules to apply within each element found by this rule's selector.
    sub_selectors: List['ScrapingRule'] = field(default_factory=list)

    # Helper method for converting to dict, handling nesting
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "selector": self.selector,
            "description": self.description,
            "extraction_type": self.extraction_type,
            "attribute_name": self.attribute_name,
            "is_list": self.is_list,
            "data_type": self.data_type,
            "required": self.required,
            "sub_selectors": [sub.to_dict() for sub in self.sub_selectors]
        }

    # Helper method for creating from dict, handling nesting
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScrapingRule':
        sub_selectors = [cls.from_dict(sub_data) for sub_data in data.get("sub_selectors", [])]
        # Make a copy of data and remove sub_selectors to avoid passing it as a keyword argument twice
        data_copy = data.copy()
        data_copy.pop("sub_selectors", None)
        return cls(**data_copy, sub_selectors=sub_selectors)


@dataclass
class ProjectConfig:
    """Project configuration for a specific scraping target."""
    id: str
    name: str
    description: str
    domain: str # e.g., 'tennis_stats', 'ecommerce', 'news'
    target_websites: List[str]
    # NEW: Add a dedicated output directory per project!
    output_directory: Optional[str] = None
    scraping_rules: List[ScrapingRule] = field(default_factory=list)
    output_settings: Dict[str, Any] = field(default_factory=lambda: {"format": "jsonl"})
    rate_limiting: Dict[str, Any] = field(default_factory=lambda: {"delay": 2.0, "respect_robots": True})
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "target_websites": self.target_websites,
            "output_directory": self.output_directory, # Add to serialization
            "scraping_rules": [rule.to_dict() for rule in self.scraping_rules],
            "output_settings": self.output_settings,
            "rate_limiting": self.rate_limiting,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectConfig':
        scraping_rules = [ScrapingRule.from_dict(rule_data) for rule_data in data.get("scraping_rules", [])]
        data_copy = data.copy()
        data_copy.pop("scraping_rules", None)
        # Filter kwargs to only include fields defined in the dataclass
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data_copy.items() if k in known_fields}
        return cls(**filtered_data, scraping_rules=scraping_rules)