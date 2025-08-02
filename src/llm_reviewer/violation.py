"""Violation dataclass."""

from dataclasses import dataclass


@dataclass(repr=False)
class Violation:
    """Violation dataclass that represents the result of the LLM review."""

    original_code: str
    proposed_code: str
    diff: str
    explanation: str
    suggestion: str

    def __repr__(self) -> str:
        """Return a string representation of the violation."""
        as_str: str = (
            f'Explanation: {self.explanation}\n',
            f'Suggestion: {self.suggestion}\n',
            f'Original code:\n{self.original_code}\n',
            f'Proposed code:\n{self.proposed_code}\n' f'Diff:\n{self.diff}\n',
        )
        return as_str
