# Introduction

This project contains Python scripts to
* Run prompts using Azure OpenAI GPT to classify a genetics functional paper (or papers)
* Post process answers from Azure OepnAI GPT for final classification using regular expressions

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

## Project Structure

 * /logs - stores execution log files
 * /results - stores execution result files
 * /configs/files - configs for paper input paremeters
 * /configs/questions - configs for system message and questions
 * /PDF-files - genetics functional papers
 * /utils - utility functions
 * execute_prompts.py - main program to process functional papers
 * outcome_post_process.py - program to post process for final classification

# Classification: Paper Processing
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
# Classification: Post Processing
## Usage
```
usage: python outcome_post_processing.py [--outcomeFile]

required arguments:
  --outcomeFile             CSV file that captures execution results
```
## Examples
### Post process a results file
```
# Adds a new column "Processed Answer" to the results file
python outcome_post_processing.py \
    --outcomeFile='result/prompt_execution_result-2023_12_05-10_24_16_AM.csv' \
```
# Development
If you install any new packages, make sure to update requirements.txt:
```
pip freeze > requirements.txt
```
