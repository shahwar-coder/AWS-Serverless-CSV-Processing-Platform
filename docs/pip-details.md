# Pip Details

Commands for setting up and managing the local Python environment.

## Create Virtual Environment With Python 3.11

```bash
py -3.11 -m venv .serverless-csv
```

## Activate The Environment

```bash
.serverless-csv\Scripts\Activate.ps1
```

## Upgrade Pip

```bash
python -m pip install --upgrade pip
```

## Create Requirements File

Generate `requirements.txt` from the current environment:

```bash
pip freeze > requirements.txt
```

## Notes

- Use `python -m pip` when possible so the command targets the active environment.
- If the environment is already created in this repo, reuse `.serverless-csv` instead of creating a new one.
