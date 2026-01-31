"""
Main PDF Parser Service
Uses PDFPlumber for parsing
"""
import time
import pdfplumber
from pathlib import Path
from typing import Optional, Literal, Dict, List
from datetime import datetime

from .config import config
from .models import ParsingResult, StatementData
from .transaction_extractor import TransactionExtractor
from .password_manager import get_pdf_password


class PDFParserService:
    """
    PDF Parser Service using PDFPlumber
    """
    
    def __init__(self):
        """Initialize parser service"""
        self.extractor = TransactionExtractor()
        
        print("\n" + "="*60)
        print("PDF Parser Service Initialized")
        print("="*60)
        print(f"[OK] PDFPlumber: Available")
        print(f"[OK] LLM Classification: {'Enabled' if self.extractor.llm else 'Disabled'}")
        print("="*60 + "\n")
    
    def _parse_with_pdfplumber(self, pdf_path: Path, password: Optional[str] = None) -> Dict:
        """Parse PDF using pdfplumber"""
        try:
            result = {
                'text_lines': [],
                'tables': [],
                'key_value_pairs': {},
                'average_confidence': 0.70
            }
            
            with pdfplumber.open(str(pdf_path), password=password) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract text
                    text = page.extract_text()
                    if text:
                        lines = text.split('\n')
                        for line in lines:
                            if line.strip():
                                result['text_lines'].append({
                                    'text': line,
                                    'confidence': 0.70,
                                    'page': page_num
                                })
                    
                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            if table:
                                result['tables'].append(table)
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Error parsing PDF with pdfplumber: {e}")
    
    def parse_statement(
        self, 
        pdf_path: str,
        password: Optional[str] = None,
        force_method: Optional[Literal["textract", "unstructured", "pdfplumber"]] = None
    ) -> ParsingResult:
        """
        Parse credit card statement PDF.
        
        Args:
            pdf_path: Path to PDF file
            password: Optional PDF password (if not provided, will try password manager)
            force_method: Force specific parsing method (skip fallback)
        
        Returns:
            ParsingResult with extracted data or error information
        """
        start_time = time.time()
        pdf_path = Path(pdf_path)
        
        # Try to get password from password manager if not provided
        if not password:
            password = get_pdf_password(str(pdf_path))
            if password:
                print(f"  [OK] Password found in secure store")
        
        print(f"\n{'='*60}")
        print(f"Parsing: {pdf_path.name}")
        print(f"{'='*60}")
        
        # Validate file
        if not pdf_path.exists():
            return self._create_error_result(
                f"File not found: {pdf_path}",
                start_time
            )
        
        if pdf_path.suffix.lower() != '.pdf':
            return self._create_error_result(
                f"Invalid file format. Expected PDF, got: {pdf_path.suffix}",
                start_time
            )
        
        # Check file size
        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
        if file_size_mb > config.max_file_size_mb:
            return self._create_error_result(
                f"File too large: {file_size_mb:.2f}MB (max: {config.max_file_size_mb}MB)",
                start_time
            )
        
        # Parse with PDFPlumber
        parsed_data = None
        parser_method = "pdfplumber"
        
        try:
            print("=> Using PDFPlumber...")
            parsed_data = self._parse_with_pdfplumber(pdf_path, password)
            print("  [OK] PDFPlumber succeeded")
        except Exception as e:
            return self._create_error_result(
                f"PDF parsing failed: {e}",
                start_time
            )
        
        if not parsed_data:
            return self._create_error_result(
                "Parsing failed with no data extracted",
                start_time
            )
        
        # Extract structured data
        print("\n=> Extracting transactions...")
        transactions = self.extractor.extract_transactions(parsed_data)
        print(f"  [OK] Extracted {len(transactions)} transactions")
        
        print("=> Extracting card metadata...")
        card_metadata = self.extractor.extract_card_metadata(parsed_data)
        
        print("=> Extracting reward points...")
        rewards = self.extractor.extract_reward_points(parsed_data)
        
        # Create StatementData
        try:
            statement_data = StatementData(
                card_metadata=card_metadata,
                transactions=transactions,
                rewards=rewards,
                statement_date=datetime.now().date(),
                source_file=pdf_path.name,
                parser_method=parser_method,
                confidence_score=parsed_data.get('average_confidence', 0.8)
            )
            
            processing_time = time.time() - start_time
            
            print(f"\n{'='*60}")
            print(f"[OK] Parsing completed successfully")
            print(f"  Method: {parser_method}")
            print(f"  Transactions: {len(transactions)}")
            print(f"  Confidence: {statement_data.confidence_score:.2%}")
            print(f"  Processing time: {processing_time:.2f}s")
            print(f"{'='*60}\n")
            
            return ParsingResult(
                success=True,
                statement_data=statement_data,
                warnings=[],
                pii_masked_fields=[],
                processing_time_seconds=processing_time
            )
            
        except Exception as e:
            return self._create_error_result(
                f"Error creating statement data: {e}",
                start_time
            )
    
    def _create_error_result(
        self,
        error_message: str,
        start_time: float
    ) -> ParsingResult:
        """Create error result"""
        processing_time = time.time() - start_time
        
        print(f"\n{'='*60}")
        print(f"[X] Parsing failed")
        print(f"  Error: {error_message}")
        print(f"  Processing time: {processing_time:.2f}s")
        print(f"{'='*60}\n")
        
        return ParsingResult(
            success=False,
            error_message=error_message,
            warnings=[],
            processing_time_seconds=processing_time
        )
    
    def batch_parse(
        self,
        pdf_directory: str,
        output_csv: Optional[str] = None
    ) -> list[ParsingResult]:
        """
        Parse multiple PDFs in a directory.
        
        Args:
            pdf_directory: Directory containing PDF files
            output_csv: Optional path to save combined results as CSV
        
        Returns:
            List of ParsingResult objects
        """
        pdf_dir = Path(pdf_directory)
        pdf_files = list(pdf_dir.glob("*.pdf"))
        
        print(f"\n{'='*60}")
        print(f"Batch Processing: {len(pdf_files)} PDF files")
        print(f"{'='*60}\n")
        
        results = []
        for pdf_file in pdf_files:
            result = self.parse_statement(str(pdf_file))
            results.append(result)
        
        # Save to CSV if requested
        if output_csv and results:
            self._save_results_to_csv(results, output_csv)
        
        # Print summary
        successful = sum(1 for r in results if r.success)
        print(f"\n{'='*60}")
        print(f"Batch Processing Complete")
        print(f"  Total: {len(results)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {len(results) - successful}")
        print(f"{'='*60}\n")
        
        return results
    
    def _save_results_to_csv(self, results: list, output_path: str):
        """Save parsing results to CSV"""
        import pandas as pd
        
        all_transactions = []
        for result in results:
            if result.success and result.statement_data:
                for txn in result.statement_data.transactions:
                    all_transactions.append({
                        'source_file': result.statement_data.source_file,
                        'date': txn.date,
                        'merchant': txn.merchant,
                        'amount': txn.amount,
                        'type': txn.transaction_type,
                        'category': txn.category,
                        'parser_method': result.statement_data.parser_method
                    })
        
        if all_transactions:
            df = pd.DataFrame(all_transactions)
            df.to_csv(output_path, index=False)
            print(f"[OK] Saved {len(all_transactions)} transactions to {output_path}")
