import logging
import re
import os
from PyPDF2 import PdfReader
from difflib import SequenceMatcher


def convert_pdf_to_txt(pdf_filepath: str) -> str:
    """
    Converts a PDF file located at the given file path into plain text

    :param pdf_filepath: location of PDF file
    :return: text extracted from PDF file
    """
    full_text = ''
    pdf_reader = PdfReader(pdf_filepath)
    for page in pdf_reader.pages:
        full_text += page.extract_text()

    # Find the reference section, and remove it (if exists)
    return __remove_reference_section(full_text)

def __remove_reference_section(text_content: str) -> str:
    # Find the reference section, and remove it (if exists)
    matching_indexes = [i.start() for i in re.finditer(r'[R|r]eferences\s*\n', text_content, re.IGNORECASE)]
    if len(matching_indexes) > 0:
        last_index = matching_indexes[-1]
        return text_content[:last_index]
    else:
        return text_content

def __similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def find_most_similar_pdf(pdf_filepath, folder_path):
    most_similar_file = None
    highest_similarity = 0

    for file in os.listdir(folder_path):
        if file.lower().endswith('.pdf'):
            sim_score = __similarity(pdf_filepath, file)

            if sim_score > highest_similarity:
                highest_similarity = sim_score
                most_similar_file = file

    if most_similar_file:
        return os.path.join(folder_path, most_similar_file)
    else:
        return None