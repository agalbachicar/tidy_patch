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

Install hadolint in Ubuntu 22.04.

```sh
sudo wget -O /bin/hadolint https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-x86_64
sudo chmod +x /bin/hadolint
```

Run pre-pre-commit checks for the entire repository.

```sh
pre-commit run --all-files
```

## Install docker configurations

1. Build docker images.

```sh
docker compose -f docker/docker-compose.yaml build
```

2. Run ollama service

```sh
docker compose -f docker/docker-compose.yaml up ollama -d
```

3. The first time, you can execute the following command that will pull and list your model.

```sh
$ docker exec -it ollama /usr/bin/bash -c /ollama/entrypoint.sh
++ ollama pull qwen2.5:1.5b
pulling manifest
pulling 183715c43589: 100% ▕███████████████████████████████████████████████████████████████████▏ 986 MB
pulling 66b9ea09bd5b: 100% ▕███████████████████████████████████████████████████████████████████▏   68 B
pulling eb4402837c78: 100% ▕███████████████████████████████████████████████████████████████████▏ 1.5 KB
pulling 832dd9e00a68: 100% ▕███████████████████████████████████████████████████████████████████▏  11 KB
pulling 377ac4d7aeef: 100% ▕███████████████████████████████████████████████████████████████████▏  487 B
verifying sha256 digest
writing manifest
success
++ ollama list
NAME            ID              SIZE      MODIFIED
qwen2.5:1.5b    65ec06548149    986 MB    Less than a second ago
```
