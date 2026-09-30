"""Read the canonical skill from a repository or a copied skill directory."""

from pathlib import Path


def skill_directory() -> Path:
    return Path(__file__).resolve().parents[2]


def load_instructions(*, include_frontmatter: bool = False) -> str:
    """Return the full instructions for an agent's instruction/system field."""
    text = (skill_directory() / "SKILL.md").read_text(encoding="utf-8")
    if include_frontmatter:
        return text
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError("SKILL.md must start with YAML frontmatter")
    return parts[2].lstrip("\r\n")
