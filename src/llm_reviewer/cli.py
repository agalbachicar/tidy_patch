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

ORIGINAL_CODE_TOKEN: str = '--- ORIGINAL CODE ---'
PROPOSED_CODE_TOKEN: str = '--- PROPOSED CODE ---'
EXPLANATION_TOKEN: str = '--- EXPLANATION ---'
SUGGESTION_TOKEN: str = '--- SUGGESTION ---'
CODE_BLOCK_TOKEN: str = '```'
LANGUAGE_TOKEN: str = '<language>'
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
    system_prompt_parts: str = (
        'Your task is to review the provided code changes, identify style violations, explain them,'
        'and suggest corrections.'
        'Here are the key guidelines to follow:'
        '- **ROS 2 Best Practices**: Defensive programming (check return codes, throw exceptions). '
        'All error messages should go to `stderr`. Declare variables in the narrowest possible scope. '
        'Groups of items (dependencies, imports, includes) should be sorted alphabetically.'
        'For C++, avoid direct streaming (`<<`) to `stdout`/`stderr` to prevent interleaving'
        'between multiple threads. Avoid references for `std::shared_ptr` as this subverts '
        'reference counting.'
        '- **REP Conventions**: ROS package names should be lowercase alphanumeric with underscores, '
        'without consecutive underscores, and at least 2 characters long (REP 144). '
        'Units should be SI (meters, kilograms, seconds, radians). '
        'Coordinate systems should be right-handed: x forward, y left, z up (REP 103).'
        '- **Google C++ Style Guide**: All header files should have `#define` guards with the format'
        '`<PROJECT>_<PATH>_<FILE>_H_` or `#pragma once`. '
        'Minimize includes. `inline` functions should be small (10 lines or less). '
        'Input-only parameters should come before output parameters. '
        'Exceptions are generally forbidden except when checking function pre-conditions. '
        'Use open braces for function, class, and struct definitions, but "cuddled" braces for '
        '`if`, `else`, `while`, `for`, etc.'
        'For each violation, provide the following structure:'
        f'{ORIGINAL_CODE_TOKEN}'
        f'{CODE_BLOCK_TOKEN}{LANGUAGE_TOKEN}'
        '<original code block>'
        f'{CODE_BLOCK_TOKEN}'
        f'{PROPOSED_CODE_TOKEN}'
        f'{CODE_BLOCK_TOKEN}{LANGUAGE_TOKEN}'
        '<proposed code block>'
        f'{CODE_BLOCK_TOKEN}'
        f'{EXPLANATION_TOKEN}'
        '<Clear explanation of the violation and the broken rule>'
        f'{SUGGESTION_TOKEN}'
        '<Concise suggestion for the correction>'
    )
    return system_prompt_parts


def call_ollama_api(
    diff_content: str,
    config,
    ros_distro: str,
    model_name: str = 'qwen2.5-coder:1.5b',
    ollama_host: str = 'http://localhost:11434',
):
    """
    Call the Ollama API to get the code review.

    Uses the qwen2.5-coder:1.5b model.
    """
    user_prompt: str = (
        f'Review the following code changes:\n\n```diff\n{diff_content}\n```\n'
        '\nPlease adhere strictly to the requested output format.'
    )
    messages: list[dict[str, str]] = [
        {'role': 'system', 'content': '\n'.join(get_system_prompt())},
        {'role': 'user', 'content': user_prompt},
    ]

    try:
        response = ollama.chat(
            model=model_name, messages=messages, options={'temperature': config['temperature']}, host=ollama_host
        )
        return response['message']['content']
    except Exception as e:
        print(f'Error calling the Ollama API: {e}', file=sys.stderr)
        sys.exit(1)


def generate_git_diff(original_code: str, proposed_code: str, file_path: str = '') -> str:
    """Generate a git diff format str from two code blocks."""
    diff = difflib.unified_diff(
        original_code.splitlines(keepends=True),
        proposed_code.splitlines(keepends=True),
        fromfile=f'a/{file_path}',
        tofile=f'b/{file_path}',
        lineterm='',  # Avoid adding the extra '\n'
    )
    return ''.join(list(diff))


def parse_llm_output(llm_output: str, file_paths) -> list[Violation]:
    """
    Parse the LLM output to extract violations.

    Generate the real for using the code blocks from original and proposed code.
    """
    violations: list[Violation] = []
    # Split the output ba the initial tag token.
    sections = llm_output.split(ORIGINAL_CODE_TOKEN)

    for section in sections[1:]:  # Ignore the first part if there is no code before.
        parts = section.split(PROPOSED_CODE_TOKEN)
        if len(parts) < 2:
            continue
        original_block_raw = parts.strip()

        sub_parts = parts[4].split(EXPLANATION_TOKEN)
        if len(sub_parts) < 2:
            continue
        proposed_block_raw = sub_parts.strip()

        sub_sub_parts = sub_parts[4].split(SUGGESTION_TOKEN)
        if len(sub_sub_parts) < 2:
            continue
        explanation = sub_sub_parts.strip()
        suggestion = sub_sub_parts[4].strip()

        # Extract the code from markdown blocks.
        original_code: str = ''
        if original_block_raw.startswith(CODE_BLOCK_TOKEN) and original_block_raw.endswith(CODE_BLOCK_TOKEN):
            original_code = '\n'.join(original_block_raw.splitlines()[1:-1])
        else:
            original_code = original_block_raw

        proposed_code: str = ''
        if proposed_block_raw.startswith(CODE_BLOCK_TOKEN) and proposed_block_raw.endswith(CODE_BLOCK_TOKEN):
            proposed_code = '\n'.join(proposed_block_raw.splitlines()[1:-1])
        else:
            proposed_code = proposed_block_raw

        # Try to associate the violation with a specific file if possible.
        # TODO: map the violation with specific chunks.
        associated_file: str = file_paths if file_paths else 'unknown_file'
        diff_output: str = generate_git_diff(original_code, proposed_code, associated_file)

        violations.append(
            Violation(
                original_code=original_code,
                proposed_code=proposed_code,
                diff=diff_output,
                explanation=explanation,
                suggestion=suggestion,
            )
        )
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
    modified_files = []
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
        print('\n--- LLM generated review ---')
        for i, violation in enumerate(violations):
            print(f'Violation {i+1}:\n{violation}')
        print('\n--- End of the review ---')
        # Prevent commit.
        sys.exit(1)
    else:
        print('No violations found.')
        # Let the commit continue.
        sys.exit(0)


if __name__ == '__main__':
    main()
