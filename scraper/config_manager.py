# scraper/config_manager.py
import yaml
import json
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, HttpUrl, Field, field_validator, model_validator

class CustomFieldConfig(BaseModel):
    name: str
    selector: str
    extract_type: str = "text"
    attribute_name: Optional[str] = None
    is_list: bool = False
    required: bool = False
    sub_selectors: Optional[List['CustomFieldConfig']] = None

    @model_validator(mode='after')
    def validate_dependencies(self) -> 'CustomFieldConfig':
        if self.extract_type == 'attribute' and not self.attribute_name:
            raise ValueError("`attribute_name` is required when `extract_type` is 'attribute'")
        if self.extract_type == 'structured_list' and not self.sub_selectors:
            raise ValueError("`sub_selectors` are required when `extract_type` is 'structured_list'")
        if self.extract_type != 'structured_list' and self.sub_selectors:
            raise ValueError("`sub_selectors` are only applicable when `extract_type` is 'structured_list'")
        return self

class SelectorConfig(BaseModel):
    title: Optional[str] = None
    main_content: Optional[str] = None
    links_to_follow: Optional[str] = None
    custom_fields: List[CustomFieldConfig] = Field(default_factory=list)

class CrawlConfig(BaseModel):
    depth: int = 0
    delay: float = Field(default=1.0, alias="delay_seconds")
    respect_robots: bool = Field(default=True, alias="respect_robots_txt")

class ExportConfig(BaseModel):
    format: str = "jsonl"
    output_path: str

class SourceConfig(BaseModel):
    name: str
    seeds: List[HttpUrl]
    source_type: Optional[str] = None
    selectors: SelectorConfig = Field(default_factory=SelectorConfig)
    crawl: CrawlConfig = Field(default_factory=CrawlConfig)
    export: ExportConfig

class DomainScrapeConfig(BaseModel):
    domain_info: Dict[str, Any] = Field(default_factory=dict)
    sources: List[SourceConfig]

class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config: Optional[DomainScrapeConfig] = self.load_config(config_path)

    def load_config(self, config_path: str) -> Optional[DomainScrapeConfig]:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
            return DomainScrapeConfig(**raw_config)
        except FileNotFoundError:
            print(f"Error: Config file not found at {config_path}")
        except (yaml.YAMLError, ValueError) as e:
            print(f"Error parsing or validating config file {config_path}: {e}")
        return None