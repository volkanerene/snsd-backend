"""
PDF Text Extraction Utilities
"""

from typing import BinaryIO
from PyPDF2 import PdfReader


async def extract_text_from_pdf(file: BinaryIO) -> str:
    """
    Extract text content from a PDF file

    Args:
        file: Binary file object (from FastAPI UploadFile)

    Returns:
        Extracted text content from all pages

    Raises:
        Exception: If PDF reading fails
    """
    try:
        reader = PdfReader(file)
        text_content = []

        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text:
                text_content.append(f"--- Page {page_num} ---\n{text}\n")

        if not text_content:
            raise ValueError("No text content found in PDF")

        return "\n".join(text_content)

    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")
