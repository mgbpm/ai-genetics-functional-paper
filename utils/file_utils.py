import re
from PyPDF2 import PdfReader

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

