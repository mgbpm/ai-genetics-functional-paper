import os
import logging
from logging import DEBUG, INFO
import argparse
from pandas import read_csv
import re
from typing import Mapping

def process_answer(row: Mapping[str, str]) -> str:
    answer = row['answer']

    found = re.search(r'"answer": "Assay Information Not Present"', answer)
    if found:
        return 'Assays Not Present'

    found = re.search(r'"answer": "Assays indicate Variant has Intermediate Function"', answer)
    if found:
        return 'Evidence of Intermediate Function'
    
    found = re.search(r'"answer": "Assays Indicate Variant Is Pathogenic"', answer)
    if found:
        return 'Pathogenic Evidence'
    
    found = re.search(r'"answer": "Assays Indicate Variant is Benign"', answer)
    if found:
        return 'Benign Evidence'
    
    found = re.search(r'"answer": "Assays are inconclusive"', answer)
    if found:
        return 'Assays are Inconclusive'
    
    return answer


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
