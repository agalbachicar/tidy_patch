"""Entry point for the package which actually process the interation with the model."""

import argparse
import sys
import json
import os
import difflib
import ollama
import subprocess
from typing import Any
from .violation import Violation


ORIGINAL_CODE_TOKEN: str = 'original_code'
PROPOSED_CODE_TOKEN: str = 'proposed_code'
DIFF_TOKEN: str = 'diff'
EXPLANATION_TOKEN: str = 'explanation'
SUGGESTION_TOKEN: str = 'suggestion'
FROM_FILE_A_TOKEN: str = 'a_filepath'
FROM_FILE_B_TOKEN: str = 'b_filepath'
DIFF_ORIGINAL_TOKEN: str = '--- a/'
DIFF_NEW_TOKEN: str = '--- b/'


def get_staged_diff() -> str:
    """Capture the difference of files in the staging area."""
    try:
        result = subprocess.run(['git', 'diff', '--staged'], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f'Error getting Git diff: {e}', file=sys.stderr)
        sys.exit(1)


def get_system_prompt() -> str:
    """Return the sytem promopt."""
    return f"""Your task is to review the provided code changes,
identify style violations, explain them, and suggest corrections.
Here are the key guidelines to follow:
- **ROS 2 Best Practices**: Defensive programming (check return codes, throw exceptions).
All error messages should go to `stderr`. Declare variables in the narrowest possible scope.
Groups of items (dependencies, imports, includes) should be sorted alphabetically.
For C++, avoid direct streaming (`<<`) to `stdout`/`stderr` to prevent interleaving
between multiple threads. Avoid references for `std::shared_ptr` as this subverts
reference counting.
- **REP Conventions**: ROS package names should be lowercase alphanumeric with underscores,
without consecutive underscores, and at least 2 characters long (REP 144).
Units should be SI (meters, kilograms, seconds, radians).
Coordinate systems should be right-handed: x forward, y left, z up (REP 103).
- **Google C++ Style Guide**: All header files should have `#define` guards with the format
`<PROJECT>_<PATH>_<FILE>_H_` or `#pragma once`.
Minimize includes. `inline` functions should be small (10 lines or less).
Input-only parameters should come before output parameters.
Exceptions are generally forbidden except when checking function pre-conditions.
Use open braces for function, class, and struct definitions, but "cuddled" braces for
`if`, `else`, `while`, `for`, etc.
Answer **only** with a json formatted string with a full list of violations.
When there are no violations, return an empty string in json format.
Each violation needs to have the following keys:
    "{ORIGINAL_CODE_TOKEN}": "<original code block>",
    "{PROPOSED_CODE_TOKEN}": "<proposed code block>",
    "{DIFF_TOKEN}": "<git diff>",
    "{EXPLANATION_TOKEN}": "<Clear explanation of the violation and the broken rule>",
    "{SUGGESTION_TOKEN}": "<Concise suggestion for the correction>",
    "{FROM_FILE_A_TOKEN}": "<File path that appears after a/ in the git diff.>",
    "{FROM_FILE_B_TOKEN}": "<File path that appears after b/ in the git diff.>"
"""


def call_ollama_api(
    diff_content: str,
    config,
    ros_distro: str,
    model_name: str = 'qwen3:4b',
    ollama_host: str = 'http://localhost:11434',
):
    """Call the Ollama API to get the code review."""
    user_prompt: str = (
        f'Review the following code changes:\n\n```diff\n{diff_content}\n```\n'
        '\nPlease adhere strictly to the requested output format.'
    )
    messages: list[dict[str, str]] = [
        {'role': 'system', 'content': get_system_prompt()},
        {'role': 'user', 'content': user_prompt},
    ]

    try:
        client: ollama.Client = ollama.Client(host=ollama_host)
        response = client.chat(
            model=model_name,
            messages=messages,
            options={'temperature': config['temperature']},
            think=False,
        )
        if response['done']:
            return response['message']['content']
        else:
            return ''
    except Exception as e:
        print(f'Error calling the Ollama API: {e}', file=sys.stderr)
        sys.exit(1)


def generate_git_diff(original_code: str, proposed_code: str, a_filepath: str, b_filepath: str) -> str:
    """Generate a git diff format str from two code blocks."""
    diff = difflib.unified_diff(
        original_code.splitlines(keepends=True),
        proposed_code.splitlines(keepends=True),
        fromfile=f'a/{a_filepath}',
        tofile=f'b/{b_filepath}',
        lineterm='',  # Avoid adding the extra '\n'
    )
    return ''.join(list(diff))


def dict_to_violation(in_dict: dict[str, str]) -> Violation:
    """Create a violation from a dictionary."""
    return Violation(
        original_code=in_dict[ORIGINAL_CODE_TOKEN],
        proposed_code=in_dict[PROPOSED_CODE_TOKEN],
        diff=in_dict[DIFF_TOKEN],
        explanation=in_dict[EXPLANATION_TOKEN],
        suggestion=in_dict[SUGGESTION_TOKEN],
        a_filepath=in_dict[FROM_FILE_A_TOKEN],
        b_filepath=in_dict[FROM_FILE_B_TOKEN],
    )


def parse_llm_output(llm_output: str, file_paths: list[str]) -> list[Violation]:
    """Parse the LLM output and return a list of violations."""
    violations: list[Violation] = []
    llm_output = llm_output[7:] if llm_output.startswith('```json') else llm_output
    llm_output = llm_output[:-3] if llm_output.endswith('```') else llm_output
    llm_output = llm_output.strip()

    violations_list = json.loads(llm_output)
    if not isinstance(violations_list, list):
        violations_list = [violations_list]

    violations = [dict_to_violation(v) for v in violations_list]

    return violations


def load_config(config_file_path: str) -> dict:
    """Load configuration from a json file."""
    if not os.path.exists(config_file_path):
        print(f'Error: file not found: {config_file_path}', file=sys.stderr)
        sys.exit(1)
    with open(config_file_path, 'r') as f:
        return json.load(f)


def parse_args() -> dict[str, Any]:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='llm-pr-reviewer',
        description='Performs a code review using an LLM of the staging are contents.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '--config-file',
        default='.llm-review-config.json',
        help='Path to the configuration file in JSON.',
    )
    parser.add_argument(
        '--ros-distro',
        default='jazzy',
        help='ROS distribution name.',
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()
    config_file = args.config_file
    ros_distro = args.ros_distro
    config = load_config(config_file)

    # Checks the files in staging.
    diff_content = get_staged_diff()
    if not diff_content.strip():
        print('There are no changes to review.')
        sys.exit(0)

    # Extract filenames form the diff to pass them to the parser.
    modified_files: list[str] = []
    for line in diff_content.splitlines():
        stripping_len = len(DIFF_ORIGINAL_TOKEN)
        if line.startswith(DIFF_ORIGINAL_TOKEN) or line.startswith(DIFF_NEW_TOKEN):
            # Extract the filename, elimnate "a/" and "b/".
            # Assert there are no duplicates when the file appears in both lines (a/ and b/).
            file_name: str = line[stripping_len:].strip()
            if file_name and file_name not in modified_files:
                modified_files.append(file_name)

    llm_output = call_ollama_api(diff_content, config, ros_distro)
    violations = parse_llm_output(llm_output, modified_files)

    if violations:
        print(f'\n--- LLM generated review. Found {len(violations)} violations. ---')
        for i, violation in enumerate(violations):
            print(f'----\nViolation {i+1}:\n{violation}\n----')
        print('\n--- End of the review ---')
        # Prevent commit.
        sys.exit(1)
    else:
        print('No violations found.')
        # Let the commit continue.
        sys.exit(0)


if __name__ == '__main__':
    main()
