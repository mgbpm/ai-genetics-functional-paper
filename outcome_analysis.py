import pandas as pd
import argparse
import os
import re
from pathlib import Path

def process_answer(answer: str) -> str:
    patterns = {
        'Assay information not present.': r'[aA]ssay\s+.*not\s+[pP]resent',
        'Assays indicate Variant has Intermediate Function.': r'[vV]ariant.*[iI]ntermediate\s+[fF]unction',
        'Assays Indicate Variant Is Pathogenic': r'[vV]ariant.*[pP]athogenic',
        'Assays Indicate Variant is Benign.': r'[vV]ariant.*[bB]enign',
        'Assays are inconclusive.': r'[vV]ariant.*[iL]nconclusive'
    }
    for outcome, pattern in patterns.items():
        if re.search(pattern, answer):
            return outcome
    return answer

def analyze_results(csv_path: Path, output_dir: Path, save_mismatches: bool):
    df = pd.read_csv(csv_path)
    df['prompt_id'] = pd.to_numeric(df['prompt_id'], errors='coerce')
    df['id_num'] = df['id'].str.extract('(\d+)', expand=False).astype(int)

    df.sort_values(by=['id_num', 'prompt_id'], ascending=[True, False], inplace=True)
    df.drop_duplicates(subset='id_num', keep='first', inplace=True)
    df.loc[:, 'processed_answer'] = df['answer'].apply(process_answer)

    accuracy = (df['processed_answer'] == df['expected_outcomes']).mean()
    print(f'Accuracy: {accuracy:.2%}')

    if save_mismatches:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f'{csv_path.stem}_mismatches.csv'
        mismatches = df[df['processed_answer'] != df['expected_outcomes']]
        columns_to_remove = ["prompt_tokens", "completion_tokens", "estimated_cost", "timestamp", "id_num"]
        mismatches_cleaned = mismatches.drop(columns=columns_to_remove)
        mismatches_cleaned.to_csv(output_path, index=False)
        print(f'Mismatches saved to {output_path}')

def main():
    parser = argparse.ArgumentParser(description='Analyze results from GPT executions')
    parser.add_argument('--csvPath', help='Path to the input CSV file', required=True, type=Path)
    parser.add_argument('--saveMismatches', help='Save mismatches to a CSV file', action='store_true')
    parser.add_argument('--outputDir', help='Directory to save the mismatches CSV file', default='mismatches', type=Path)

    args = parser.parse_args()
    assert args.csvPath.exists(), 'Input CSV file does not exist.'

    analyze_results(args.csvPath, args.outputDir, args.saveMismatches)

if __name__ == "__main__":
    main()
