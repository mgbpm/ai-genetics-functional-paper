# Introduction

This project contains Python scripts to
* Run prompts using Azure OpenAI GPT to classify a genetics functional paper (or papers)
* Post process answers from Azure OepnAI GPT for final classification using regular expressions

```
logs/                       - Stores execution log files
results/                    - Stores execution result files
configs
  files/                    - Configs for paper input paremeters
  questions/                - Configs for system message and questions
PDF-files/                  - Stores genetics functional papers
utils/                      - Utility functions
execute_prompts.py          - Main program to process functional papers
outcome_post_process.py     - Program to post process for final classification
```

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

# Prerequisites
## Functional Papers to Process
1. Gather the genetics functional papers in PDF you want to process.
2. Store the papers in a dedicated folder called `/PDF-files`.
3. Configure the location of this folder in your configuration file (e.g. configs/files/publication_params_training.xlsx)

## Configuration File for Input Parameters
1. Create an Excel file in the `/configs/files` directory.
2. The file should contain the following columns:

Column Name | Description | Example
------------|-------------|--------
id          | Unique identifier for each paper | pub-1
file_path   | Relative path to the paper's PDF file | PDF-files/training_set
file_name   | Filename of the paper's PDF file | example_paper.pdf
variant     | Target genetic variant           | c.70T>C (p.C24R)
gene        | Gene associated with the variant | BRCA1
variant_aliases | A list of nomenclature aliases equivalent to the target variant (separated by commas) | c.70T>C,70T/C,70T>C
expected_outcomes | Expected classification | Pathogenic

# Program: Paper Processing
## Usage
```
usage: python execute_prompts.py [--fileConfig] [--questionConfg]

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
## Examples
### Process a specific publication
```
python execute_prompts.py \
    --publicationId='pub-1' \
    --fileConfig='configs/files/publication_params_training.xlsx' \
    --questionConfig='configs/questions/genetics_questions-variants.json'
```
### Process all publications
```
# Process all the publications configured in the file config
# After processing each publication, wait for 5 seconds
python execute_prompts.py \
    --fileConfig='configs/files/publication_params_training.xlsx' \
    --questionConfig='configs/questions/genetics_questions-variants.json' \
    --sleepAtEachPublication=5
```
# Program: Post Processing
## Usage
```
usage: python outcome_post_processing.py [--outcomeFile]

required arguments:
  --outcomeFile             CSV file that captures execution results
```
## Examples
### Post process a results file
```
# Adds a new column "Processed Answer" to the outcome file
python outcome_post_processing.py \
    --outcomeFile='result/prompt_execution_result-2023_12_05-10_24_16_AM.csv' \
```
# Development
If you install any new packages, make sure to update requirements.txt:
```
pip freeze > requirements.txt
```
