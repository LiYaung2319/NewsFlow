from dataclasses import dataclass
from typing import Dict, Any, Optional
import json


@dataclass
class ParsedItem:
    title: str
    url: str
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "title": self.title,
            "url": self.url,
        }
        if self.source:
            result["source"] = self.source
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParsedItem":
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            source=data.get("source"),
        )
