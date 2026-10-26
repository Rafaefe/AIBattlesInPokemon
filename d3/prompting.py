"""
prompting.py -- carga los prompts versionados de d3/prompts/.

Cada agente tiene UN archivo `<agente>.vN.md`, fuera del codigo. Dentro, cada
plantilla empieza con una linea `## [nombre]`; los placeholders van entre llaves
y los rellena d3/agents.py. Los comentarios HTML (<!-- -->) son notas para el
equipo y no llegan al modelo. Cada traza guarda el archivo y su sha256, asi una
corrida queda atada a la version exacta de cada prompt.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
_SECTION = re.compile(r"^## \[(\w+)\]\s*$", re.M)


@dataclass(frozen=True)
class PromptFile:
    agent: str
    path: Path
    version: str
    sha256: str
    sections: Dict[str, str]

    def render(self, section: str, **values) -> str:
        text = self.sections[section].format(**values)
        return re.sub(r"\n{3,}", "\n\n", text).strip()     # placeholders vacios no dejan huecos

    def describe(self) -> Dict[str, str]:
        return {"file": f"d3/prompts/{self.path.name}", "version": self.version,
                "sha256": self.sha256[:12]}


def load_prompt(agent: str, version: str = "v1") -> PromptFile:
    path = PROMPT_DIR / f"{agent}.{version}.md"
    raw = path.read_text(encoding="utf-8")
    body = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    parts = _SECTION.split(body)
    sections = {parts[i]: parts[i + 1].strip("\n") for i in range(1, len(parts), 2)}
    return PromptFile(agent, path, version, hashlib.sha256(raw.encode("utf-8")).hexdigest(), sections)
