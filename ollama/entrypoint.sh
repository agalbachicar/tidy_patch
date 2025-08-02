#!/usr/bin/bash
set -ex

# Pulling this model as it is Apache 2.0 licensed.
ollama pull qwen2.5-coder:1.5b
# Debug output.
ollama list
