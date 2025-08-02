"""Hold prompts and useful constants."""


class Tokens:
    """Class to hold general tokens used in the prompts and violations."""

    ORIGINAL_CODE_TOKEN: str = 'original_code'
    PROPOSED_CODE_TOKEN: str = 'proposed_code'
    DIFF_TOKEN: str = 'diff'
    EXPLANATION_TOKEN: str = 'explanation'
    SUGGESTION_TOKEN: str = 'suggestion'
    FROM_FILE_A_TOKEN: str = 'a_filepath'
    FROM_FILE_B_TOKEN: str = 'b_filepath'


def _get_violations_format_str() -> str:
    """Return the final part of the request which sets the violations output format."""
    return f"""Answer **only** with a json formatted string with a full list of violations.
When there are no violations, return an empty string in json format.
Each violation needs to have the following keys:
    "{Tokens.ORIGINAL_CODE_TOKEN}": "<original code block>",
    "{Tokens.PROPOSED_CODE_TOKEN}": "<proposed code block>",
    "{Tokens.DIFF_TOKEN}": "<git diff>",
    "{Tokens.EXPLANATION_TOKEN}": "<Clear explanation of the violation and the broken rule>",
    "{Tokens.SUGGESTION_TOKEN}": "<Concise suggestion for the correction>",
    "{Tokens.FROM_FILE_A_TOKEN}": "<File path that appears after a/ in the git diff.>",
    "{Tokens.FROM_FILE_B_TOKEN}": "<File path that appears after b/ in the git diff.>"
"""


def get_general_expert_prompt() -> str:
    """Return the sytem promopt for a general software engineer."""
    return f"""You are an expert C++ and Python software engineer.
Your task is to review a patch and identify violations to different styleguides
and best practices for C++ and Python code. Note that each patch may have more
than one violation, so provide specific results for each identified violations.

For C++, focus on the following sources:
- Google C++ Style Guide.
- C++ Core Guidelines.

For Python, focus on the following sources:
- PEP 8, the Style Guide for Python Code
- Google Python Style Guide.

Consider identifying anti-patterns and propose a better alternative. Do this only
when there is a high confidence.

{_get_violations_format_str()}
"""
