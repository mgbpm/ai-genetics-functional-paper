import pandas as pd
import argparse
from pathlib import Path
import re
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix

def process_answer(answer: str) -> str:
    patterns = {
        'Not present': r'[aA]ssay\s+.*not\s+[pP]resent',
        'Intermediate': r'[vV]ariant.*[iI]ntermediate\s+[fF]unction',
        'Pathogenic': r'[vV]ariant.*[pP]athogenic',
        'Benign': r'[vV]ariant.*[bB]enign',
        'Inconclusive': r'[aA]ssay.*[iL]nconclusive'
    }
    for outcome, pattern in patterns.items():
        if re.search(pattern, answer):
            return outcome
    return "Others"

def load_and_preprocess_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df['prompt_id'] = pd.to_numeric(df['prompt_id'], errors='coerce')
    df['id_num'] = df['id'].str.extract('(\d+)', expand=False).astype(int)
    df.sort_values(by=['id_num', 'prompt_id'], ascending=[True, False], inplace=True)
    return df.drop_duplicates(subset='id_num', keep='first')

def visualize_confusion_matrix(df: pd.DataFrame, output_path: Path):
    labels = ['Not present', 'Intermediate', 'Pathogenic', 'Benign', 'Inconclusive', 'Others']
    cm = confusion_matrix(df['expected_outcomes'], df['processed_answer'], labels=labels)

    plt.figure(figsize=(12, 10))
    ax = sns.heatmap(cm, annot=True, fmt='d', xticklabels=labels, yticklabels=labels,
                     cmap='Blues', annot_kws={"size": 14})
    plt.title('Confusion Matrix', fontsize=18)
    plt.ylabel('True Label', fontsize=16)
    plt.xlabel('Predicted Label', fontsize=16)
    ax.set_yticklabels(labels, rotation=0)  # Rotate y-axis labels
    ax.set_xticklabels(labels, rotation=30)  # Rotate y-axis labels
    plt.savefig(output_path)

def analyze_results(args):
    df = load_and_preprocess_data(args.csvPath)
    df['processed_answer'] = df['answer'].apply(process_answer)
    df['expected_outcomes'] = df['expected_outcomes'].apply(process_answer)

    accuracy = (df['processed_answer'] == df['expected_outcomes']).mean()
    print(f"Accuracy: {accuracy:.2%} ({(df['processed_answer'] == df['expected_outcomes']).sum()}/{len(df)})")

    if args.saveMismatches:
        args.outputDir.mkdir(parents=True, exist_ok=True)
        mismatches = df[df['processed_answer'] != df['expected_outcomes']]
        columns_to_remove = ["prompt_tokens", "completion_tokens", "estimated_cost", "timestamp", "id_num"]
        output_path = args.outputDir / f'{args.csvPath.stem}_mismatches.csv'
        mismatches.drop(columns=columns_to_remove).to_csv(output_path, index=False)
        print(f"Mismatches saved to {output_path}")

    if args.visualize:
        output_path = args.outputDir / f'{args.csvPath.stem}_confusion_matrix.png'
        visualize_confusion_matrix(df, output_path)
        print(f"Confusion Matrix saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Analyze results from GPT executions')
    parser.add_argument('--csvPath', type=Path, required=True, help='Path to the input CSV file')
    parser.add_argument('--saveMismatches', action='store_true', help='Save mismatches to a CSV file')
    parser.add_argument('--outputDir', type=Path, default='analysis', help='Directory to save the analysis files')
    parser.add_argument('--visualize', action='store_true', help='Visualize the results with a confusion matrix')
    args = parser.parse_args()

    if not args.csvPath.exists():
        raise FileNotFoundError('Input CSV file does not exist.')
    analyze_results(args)

if __name__ == "__main__":
    main()
