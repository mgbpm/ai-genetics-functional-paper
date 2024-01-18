import os
import logging
from logging import DEBUG, INFO
import argparse
from pandas import read_csv
import re
from typing import Mapping

def process_answer(row: Mapping[str, str]) -> str:
    answer = row['answer']

    found = re.search(r'"answer": "No", "details": "Assay Information Not Present"', answer, re.IGNORECASE)
    if found:
        return 'No Assays'

    found = re.search(r'"answer": "Assays indicate Variant has Intermediate Function"', answer, re.IGNORECASE)
    if found:
        return 'Intermediate'
    
    found = re.search(r'"answer": "Assays Indicate Variant Is Pathogenic"', answer, re.IGNORECASE)
    if found:
        return 'Pathogenic'
    
    found = re.search(r'"answer": "Assays Indicate Variant is Benign"', answer, re.IGNORECASE)
    if found:
        return 'Benign'
    
    found = re.search(r'"answer": "Assays are inconclusive"', answer, re.IGNORECASE)
    if found:
        return 'Inconclusive'
    
    found = re.search(r'"answer": "Cannot classify"', answer, re.IGNORECASE)
    if found:
        return 'Cannot Classify'
    
    return ''


def main():
    parser = argparse.ArgumentParser(
        description='Post process outcome from sequential prompts')
    parser.add_argument(
        '--outcomeFile', help='file with outcomes from sequential prompts', required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        handlers=[
                            logging.FileHandler(
                                os.path.join('logs', 'outcome-post-processor.log'), 'w+'),
                            logging.StreamHandler()
                        ])

    data = read_csv(args.outcomeFile)
    # Add a new column in the result file for the processed answer
    data['processed_answer'] = data.apply(lambda row: process_answer(row), axis=1)
    data.to_csv(args.outcomeFile, index=False)

if __name__ == "__main__":
    main()
