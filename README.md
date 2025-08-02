# tidy_patch

LLM based tool that suggests edits to your code patches based on your rule styles. It goes one step further than conventional static analyzers by incorporating code conventions for which there are no linters but human intervention.

## Developing

Install pre-commit dependency.

```sh
pip install pre-commit
```

Install pre-commit:

```sh
pre-commit install
```

Run pre-pre-commit checks for the entire repository.

```sh
pre-commit run --all-files
```
