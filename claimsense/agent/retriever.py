"""Policy Document Indexer & Clause Retriever.

Parses numbered clauses from policy files in data_gen/policy_docs/*.txt
and provides fast, lightweight TF-IDF / keyword similarity retrieval.
Designed to run reliably on Streamlit Community Cloud with zero C-extension overhead.
"""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Dict, List, Optional
from claimsense.config import get_settings


class PolicyClause:
    def __init__(self, clause_id: str, policy_type: str, section: str, text: str):
        self.clause_id = clause_id
        self.policy_type = policy_type.upper()
        self.section = section
        self.text = text
        self.tokens = self._tokenize(f"{clause_id} {section} {text}")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        words = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower())
        return words


class PolicyRetriever:
    """Indexes policy documents and retrieves top matching clauses by relevance."""

    def __init__(self, docs_dir: Optional[Path] = None):
        settings = get_settings()
        self.docs_dir = docs_dir or (settings.DATA_GEN_PATH / "policy_docs")
        self.clauses: List[PolicyClause] = []
        self._load_and_index()

    def _load_and_index(self) -> None:
        """Parses clause files."""
        if not self.docs_dir.exists():
            return

        for p in self.docs_dir.glob("*.txt"):
            policy_type = "AUTO"
            if "health" in p.name.lower():
                policy_type = "HEALTH"
            elif "home" in p.name.lower():
                policy_type = "HOME"

            current_section = "GENERAL"
            with open(p, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("="):
                        continue
                    if line.startswith("[SECTION"):
                        current_section = line.strip("[]")
                        continue

                    # Look for [CLAUSE-ID] Text pattern
                    match = re.match(r"^\[([A-Z0-9\-]+)\]\s*(.*)", line)
                    if match:
                        cid, ctext = match.groups()
                        clause = PolicyClause(
                            clause_id=cid,
                            policy_type=policy_type,
                            section=current_section,
                            text=ctext,
                        )
                        self.clauses.append(clause)

    def retrieve(self, query: str, policy_type: str, top_k: int = 4) -> List[Dict[str, str]]:
        """Retrieves top matching clauses for a specific policy type."""
        p_type = policy_type.strip().upper()
        query_tokens = set(PolicyClause._tokenize(query))

        candidates = [c for c in self.clauses if c.policy_type == p_type]
        if not candidates:
            candidates = self.clauses

        scored: List[tuple[float, PolicyClause]] = []
        for c in candidates:
            overlap = query_tokens.intersection(c.tokens)
            score = len(overlap) / (math.sqrt(len(c.tokens)) + 1e-5)
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_clauses = scored[:top_k]

        return [
            {
                "clause_id": c.clause_id,
                "policy_type": c.policy_type,
                "section": c.section,
                "text": c.text,
                "relevance_score": f"{score:.2f}",
            }
            for score, c in top_clauses
        ]

    def get_all_clause_ids(self) -> List[str]:
        """Returns list of all known valid clause identifiers."""
        return [c.clause_id for c in self.clauses]


_retriever_instance: Optional[PolicyRetriever] = None


def get_policy_retriever() -> PolicyRetriever:
    """Singleton getter for PolicyRetriever."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = PolicyRetriever()
    return _retriever_instance
