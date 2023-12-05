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
    reference_indexes = [i.start() for i in re.finditer(r'[R|r]eferences\s*\n', text_content, re.IGNORECASE)]

    if len(reference_indexes) > 0:
        last_ref_index = reference_indexes[-1]
        updated_content = text_content[:last_ref_index]

        # Find first table that comes after the reference section
        table_index = __find_element_after_index(text_content, r'Table \d+\.', last_ref_index)

        # Find first figure that comes after the reference section
        figure_index = __find_element_after_index(text_content, r'(?:Figure|Fig\.)\s?(\d+)', last_ref_index)

        # if there're supplemental tables/figures after the reference section
        supp_index = 0
        if table_index > last_ref_index and figure_index > last_ref_index:
            supp_index = min(table_index, figure_index)
        else:
            supp_index = max(last_ref_index, max(table_index, figure_index))
        
        if supp_index > last_ref_index:
            updated_content += '\n' + text_content[supp_index:]

        return updated_content
    else:
        return text_content
    
def __find_element_after_index(text_content: str, element_regex: str, after_index: int) -> int:
    matching_indexes = [i.start() for i in re.finditer(element_regex, text_content, re.IGNORECASE)]

    return next(i for i in matching_indexes if i > after_index) \
            if len(matching_indexes) > 0 and matching_indexes[-1] > after_index else 0
