# Introduction

This project contains an example Jupyter notebook and Python script to run a set of prompts on the content of a PDF file.

# Getting started

## Install Python and required modules

* Install python 3.8+ https://www.python.org/downloads/
* Install poppler (PDF rendering library) https://poppler.freedesktop.org/
* Create a new Python virtual environment venv
* Activate the new Python virtual environment
* Install the Python modules listed in [requirements.txt](requirements.txt) to the Python virtual environment venv

On Mac:
```shell
brew install poppler

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment variables

* Create a file named '.env'
* Copy over environment variables from .env-examples
* Specify values for the environment variables

# Usage
```
usage: python execute_prompts.py

required arguments:
  --fileConfig              Excel file that contains publication parameters
  --questionConfg           Json file that contains a system message, a list of questions along with their stop conditions

optional arguments:
  -h, --help                Show help message and exit
  --publicationId           Id of the publication to process
  --sleepAtEachPublication  If specified, wait x number of seconds before processing the next publication
  --useMock                 Indicates to use a mock service instead of calling OpenAI
  --debug                   Sets logger level to DEBUG
  --temperature             GPT model - temperature setting
  --maxTokens               GPT model - max # of tokens in response
```
# Examples
## Process a specific publication
```
python execute_prompts.py \
    --publicationId='pub-1' \
    --fileConfig='configs/files/publication_params_training.xlsx' \
    --questionConfig='configs/questions/genetics_questions-variants.json'
```
## Process all publications
```
# Process all the publications configured in the file config
# After processing each publication, wait for 5 seconds
python execute_prompts.py \
    --fileConfig='configs/files/publication_params_training.xlsx' \
    --questionConfig='configs/questions/genetics_questions-variants.json' \
    --sleepAtEachPublication=5
```
# Development
If you install any new packages, make sure to update requirements.txt:
```
pip freeze > requirements.txt
```
