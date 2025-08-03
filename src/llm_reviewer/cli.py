"""Entry point for the package which actually process the interation with the model."""

import argparse
import sys
import json
import os
import difflib
import ollama
import subprocess
from typing import Any
from .prompt import (
    get_general_expert_prompt,
    Tokens,
)
from .violation import Violation


EXTENSIONS_TO_CHECK: tuple = ('.py', '.h', '.hh', '.hpp', '.hxx', '.c', '.cc', '.cpp', '.cxx')


def get_staged_diff(filepath: str = '') -> str:
    """Capture the difference of files in the staging area."""
    cmd: list[str] = ['git', 'diff', '--staged']
    if filepath:
        cmd.append(filepath)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f'Error getting Git diff: {e}', file=sys.stderr)
        sys.exit(1)


def get_staged_diff_files() -> list[str]:
    """Capture the list of files in the staging area."""
    try:
        result = subprocess.run(['git', 'diff', '--name-only', '--staged'], capture_output=True, text=True, check=True)
        return result.stdout.strip().split('\n')
    except subprocess.CalledProcessError as e:
        print(f'Error getting Git diff: {e}', file=sys.stderr)
        sys.exit(1)


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
        {'role': 'system', 'content': get_general_expert_prompt()},
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
        original_code=in_dict[Tokens.ORIGINAL_CODE_TOKEN],
        proposed_code=in_dict[Tokens.PROPOSED_CODE_TOKEN],
        diff=in_dict[Tokens.DIFF_TOKEN],
        explanation=in_dict[Tokens.EXPLANATION_TOKEN],
        suggestion=in_dict[Tokens.SUGGESTION_TOKEN],
        a_filepath=in_dict[Tokens.FROM_FILE_A_TOKEN],
        b_filepath=in_dict[Tokens.FROM_FILE_B_TOKEN],
    )


def parse_llm_output(llm_output: str) -> list[Violation]:
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
        '--exit-zero',
        default=False,
        help='Make the program always return zero regardless of the review result.',
        action='store_true',
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
    config_file: str = args.config_file
    ros_distro: str = args.ros_distro
    force_exit_zero: bool = args.exit_zero
    exit_result: int = 0

    config = load_config(config_file)

    # Extract filenames form the diff to pass them to the parser.
    modified_files: list[str] = get_staged_diff_files()
    modified_files[:] = [f for f in modified_files if f.endswith(EXTENSIONS_TO_CHECK)]

    # Create individual diff chunks for each file to have more
    # precide response from the LLM and reduce the context size as well.
    diff_chunks: list[str] = list(map(get_staged_diff, modified_files))
    diff_chunks[:] = [x for x in diff_chunks if x]

    # Make multiple calls for each file difference.
    violations: list[Violation] = []
    for diff_chunk in diff_chunks:
        llm_output = call_ollama_api(diff_chunk, config, ros_distro)
        violations.extend(parse_llm_output(llm_output))

    print(f'\n--- LLM generated review. Found {len(violations)} violations. ---', file=sys.stderr)
    if violations:
        for i, violation in enumerate(violations):
            print(f'----\nViolation {i+1}:\n{violation}\n----', file=sys.stderr)
        exit_result = 1
    else:
        exit_result = 0
    print('\n--- End of the review ---', file=sys.stderr)

    sys.exit(exit_result if not force_exit_zero else 0)


if __name__ == '__main__':
    main()
