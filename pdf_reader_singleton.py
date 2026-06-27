# pdf_reader_singleton.py
"""
Singleton pattern for PDFReader to ensure only one instance exists
and suppliers are loaded once and shared across the application.
"""

import logging
from pdf_reader import PDFReader

logger = logging.getLogger(__name__)


class PDFReaderSingleton:
    """
    Singleton wrapper for PDFReader to ensure only one instance exists
    across the entire application.
    """
    _instance = None
    _reader = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PDFReaderSingleton, cls).__new__(cls)
            cls._reader = PDFReader()
            logger.info("PDFReader singleton instance created")
        return cls._instance
    
    @classmethod
    def get_instance(cls):
        """Get the singleton PDFReader instance."""
        if cls._instance is None:
            cls()
        return cls._reader
    
    @classmethod
    def refresh_suppliers(cls):
        """Refresh supplier list from database."""
        if cls._reader:
            cls._reader.vendor_keywords = cls._reader._load_supplier_names()
            logger.info(f"Suppliers refreshed: {len(cls._reader.vendor_keywords)} loaded")
            return True
        return False
    
    @classmethod
    def get_suppliers(cls):
        """Get current supplier list."""
        if cls._reader:
            return cls._reader.vendor_keywords
        return []
    
    @classmethod
    def reset(cls):
        """Reset the singleton (useful for testing)."""
        cls._instance = None
        cls._reader = None


# Convenience function for easy import
def get_pdf_reader():
    """Get the shared PDFReader instance."""
    return PDFReaderSingleton.get_instance()