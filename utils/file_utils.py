import re
import os
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract
import logging


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


# def save_pdf_to_png(pdf_path):
#     pages= convert_from_path(pdf_path, 500)
#     file_paths = []
#     for count, page in enumerate(pages):
#         file_path = f'utils/output2/{count}.png'
#         page.save(file_path, 'png')
#         file_paths.append(file_path)

#     return file_paths

def extract_text_from_pdf(pdf_filepath: str, lang: str = 'eng') -> str:
    logging.info(f'Processing PDF: {pdf_filepath}')
    base, ext = os.path.splitext(pdf_filepath)
    text_filepath = base + ".txt"

    # Convert PDF to images
    pages = convert_from_path(pdf_filepath, 500)

    try:
        # Use OCR to extract text from images
        original_text = ''
        for page in pages:
            original_text += pytesseract.image_to_string(page, lang=lang) + '\n'
        # Remove reference section
        ref_removed_text = __remove_reference_section(original_text)

        # Save the extracted text to a file
        with open(text_filepath, 'w') as file:
            file.write(ref_removed_text)
        logging.info(f'Extracted text saved to: {text_filepath}')
        return ref_removed_text
    except Exception as ex:
        if hasattr(ex, 'message'):
            error_message = "[ERROR] Unable to process file: {0}".format(ex.message)
        else:
            error_message = "[ERROR] Unable to process file: {0}".format(str(ex))

        logging.error(error_message)
        raise ex


def get_file_content(txt_filepath: str) -> str:
    logging.info(f'Getting content of: {txt_filepath}')

    with open(txt_filepath, 'r', encoding='utf-8') as file:
        original_text = file.read()

    # Remove reference section
    return __remove_reference_section(original_text)


def __remove_reference_section(text_content: str) -> str:
    # Find the reference section, and remove it (if exists)
    matching_indexes = [i.start() for i in re.finditer(r'[R|r]eferences\s*\n', text_content, re.IGNORECASE)]
    if len(matching_indexes) > 0:
        last_index = matching_indexes[-1]
        return text_content[:last_index]
    else:
        return text_content
