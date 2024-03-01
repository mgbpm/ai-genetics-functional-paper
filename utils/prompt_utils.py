import json
import re
import logging
from typing import Dict


class NodeMissingError(Exception):
    """Custom exception raised when a specific node does not in the questions graph."""

    def __init__(self, message):
        """
        Args:
            message (str): The error message to be included in the exception.
        """
        super().__init__(message)


class CycleDetectedError(Exception):
    """Custom exception raised when a cycle is detected in the questions graph."""

    def __init__(self, message):
        """
        Args:
            message (str): The error message to be included in the exception.
        """
        super().__init__(message)


def load_questions_config(file_path: str) -> Dict:
    """Loads questions from the JSON file."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data


def has_node(questions: Dict, start_id: str) -> bool:
    """
    Checks if the given list of questions contains a key with the start id
    """
    return start_id in questions


def has_cycle(questions: Dict, start_id: str) -> bool:
    """
    Checks if there is a cycle in the questions graph.

    Note that this only checks all "true" and all "false" paths in the graph.

    This method is not meant to check all possible paths in the graph
    by considering different outcomes of the answer conditions.
    """
    visited = set()

    def _has_cycle_helper(question_id, next_question_field):
        if question_id in visited:
            return True
        visited.add(question_id)

        next_id = questions[question_id].get(next_question_field)
        if next_id and _has_cycle_helper(next_id, next_question_field):
            return True

        return False

    if not _has_cycle_helper(start_id, 'next_question_true'):
        visited = set()
        return _has_cycle_helper(start_id, 'next_question_false')
    else:
        return True


def get_next_question(questions: Dict, question_id: str, answer: str) -> str:
    """Gets the next question based on the condition and answer."""
    question = questions[question_id]

    # Get ID of the next question
    regex = question['answer_condition']
    logging.info(f"Answer Condition: {regex}, Answer: {answer}")
    # Check if the answer condition is satisfied (if exists)
    if regex is None or re.search(regex, answer):
        logging.info(f"Question ID: {question_id}, Condition: True")
        return question.get('next_question_true')
    else:
        logging.info(f"Question ID: {question_id}, Condition: False")
        return question.get('next_question_false')
