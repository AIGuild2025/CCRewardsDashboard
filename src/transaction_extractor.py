"""
Transaction Extractor with LLM-assisted classification
"""
import re
import json
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from .config import config
from .models import Transaction, CardMetadata, RewardPoints


class TransactionExtractor:
    """
    Extracts transaction data from parsed PDF content.
    Uses LLM for transaction classification.
    """
    
    def __init__(self):
        """Initialize extractor with LLM"""
        self.llm = None
        
        if config.groq_api_key:
            try:
                self.llm = ChatGroq(
                    model=config.groq_model,
                    temperature=config.llm_temperature,
                    groq_api_key=config.groq_api_key
                )
                print(f"[OK] LLM initialized for classification (Groq: {config.groq_model})")
            except Exception as e:
                print(f"[WARN] Could not initialize LLM: {e}")
    
    def extract_transactions(
        self, 
        parsed_data: Dict,
        use_llm_classification: bool = True
    ) -> List[Transaction]:
        """
        Extract transactions from parsed PDF data.
        
        Args:
            parsed_data: Output from parser (Textract/Unstructured/PDFPlumber)
            use_llm_classification: Whether to use LLM for categorization
        
        Returns:
            List of Transaction objects
        """
        transactions = []
        
        # For PDFPlumber, text extraction often works better than tables for complex PDFs
        # Try text first, then supplement with tables
        if parsed_data.get('text_lines'):
            text_transactions = self._extract_from_text(parsed_data['text_lines'])
            transactions.extend(text_transactions)
            print(f"[DEBUG] Extracted {len(text_transactions)} from text")
        
        # Also try tables (for credit transactions that PDFPlumber CAN parse)
        if parsed_data.get('tables'):
            table_transactions = self._extract_from_tables(parsed_data['tables'])
            # Deduplicate by date+merchant+amount
            existing = {(t.date, t.merchant, t.amount) for t in transactions}
            new_table_txns = [t for t in table_transactions 
                            if (t.date, t.merchant, t.amount) not in existing]
            transactions.extend(new_table_txns)
            print(f"[DEBUG] Extracted {len(table_transactions)} from tables ({len(new_table_txns)} unique)")
        
        # LLM classification for categories
        if use_llm_classification and self.llm and transactions:
            print(f"\n=> Classifying transactions with LLM...")
            transactions = self._classify_with_llm(transactions)
            print(f"  [OK] Classified {len(transactions)} transactions")
        
        return transactions
    
    def _extract_from_tables(self, tables: List[List[List[str]]]) -> List[Transaction]:
        """Extract transactions from table data"""
        transactions = []
        
        # Strategy: Find header once, then apply to ALL tables with matching column count
        header_row = None
        col_indices = None
        
        # First pass: Find the header
        for table in tables:
            if not table or len(table) == 0:
                continue
            
            first_row = [str(cell).lower() for cell in table[0]]
            potential_col_map = self._identify_transaction_columns(first_row)
            
            if potential_col_map:
                header_row = table[0]
                col_indices = potential_col_map
                print(f"[DEBUG] Found header with {len(header_row)} cols, amount at index {col_indices.get('amount', 'N/A')}")
                break
        
        if not col_indices:
            return transactions
        
        # Second pass: Extract from ALL tables matching column structure
        for table in tables:
            if not table:
                continue
            
            for row_idx, row in enumerate(table):
                # Skip if not enough columns
                if len(row) != len(header_row):
                    continue
                
                # Skip header rows
                if row == header_row:
                    continue
                
                # Try to parse as data row
                try:
                    if self._is_data_row(row, col_indices):
                        transaction = self._parse_transaction_row(row, col_indices)
                        if transaction:
                            transactions.append(transaction)
                except Exception as e:
                    # Silently skip unparseable rows
                    continue
        
        return transactions
    
    def _is_data_row(self, row: List[str], col_indices: Dict[str, int]) -> bool:
        """Check if row contains transaction data (not a header)"""
        try:
            date_col = row[col_indices['date']].strip() if 'date' in col_indices else ""
            desc_col = row[col_indices['description']].strip() if 'description' in col_indices else ""
            
            # Check if date column looks like a date (DD/MM/YYYY or YYYY-MM-DD)
            has_date = bool(re.match(r'\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2}', date_col))
            
            # Description should exist and not be a header
            desc_lower = desc_col.lower()
            is_not_header = (len(desc_col) > 0 and 
                           'transaction' not in desc_lower and 
                           'details' not in desc_lower and 
                           'particular' not in desc_lower and
                           'serno' not in desc_lower)
            
            result = has_date and is_not_header
            
            # Debug: print rejected rows
            if not result and has_date:
                print(f"[DEBUG] Rejected row: date={date_col}, desc={desc_col[:40]}, reason={'no_date' if not has_date else 'header_like'}")
            
            return result
            
        except (IndexError, KeyError) as e:
            return False
    
    def _identify_transaction_columns(self, header: List[str]) -> Dict[str, int]:
        """Identify which columns contain transaction data"""
        col_map = {}
        
        # Common column name patterns
        date_patterns = ['date', 'txn date', 'transaction date', 'posting date']
        desc_patterns = ['description', 'particulars', 'details', 'merchant', 'narration']
        amount_patterns = ['amount', 'debit', 'credit', 'transaction amount']
        # Columns to EXCLUDE from amount detection
        exclude_patterns = ['reward', 'points', 'miles', 'intl', 'international', 'serno', 'serial']
        
        for i, col_name in enumerate(header):
            col_lower = col_name.lower().strip().replace('\n', ' ')
            
            # Skip columns that are definitely not amounts
            if any(exclude in col_lower for exclude in exclude_patterns):
                continue
            
            if any(pattern in col_lower for pattern in date_patterns) and 'date' not in col_map:
                col_map['date'] = i
            elif any(pattern in col_lower for pattern in desc_patterns) and 'description' not in col_map:
                col_map['description'] = i
            elif any(pattern in col_lower for pattern in amount_patterns):
                if 'debit' in col_lower or 'dr' in col_lower:
                    col_map['debit'] = i
                elif 'credit' in col_lower or 'cr' in col_lower:
                    col_map['credit'] = i
                elif 'amount' not in col_map:
                    # Prefer columns explicitly mentioning currency or amount
                    if 'in' in col_lower or '₹' in col_name or 'inr' in col_lower or 'rupee' in col_lower:
                        col_map['amount'] = i
                    elif 'amount' not in col_map:  # Fallback
                        col_map['amount'] = i
        
        # If no amount column found but we have date and description, try rightmost numeric column
        if 'amount' not in col_map and 'date' in col_map and 'description' in col_map:
            # Scan from right to find last column that looks like amounts
            for i in range(len(header) - 1, -1, -1):
                col_lower = header[i].lower().strip().replace('\n', ' ')
                if any(exclude in col_lower for exclude in exclude_patterns):
                    continue
                # Check if it mentions currency/amount
                if 'amount' in col_lower or '₹' in header[i] or 'in' in col_lower:
                    col_map['amount'] = i
                    break
        
        # Validate essential columns are present
        if 'date' in col_map and 'description' in col_map:
            return col_map
        
        return {}
    
    def _parse_transaction_row(self, row: List[str], col_indices: Dict[str, int]) -> Optional[Transaction]:
        """Parse a single transaction row"""
        try:
            # Extract date
            date_str = row[col_indices['date']].strip()
            if not date_str:
                return None
            
            # Extract description/merchant
            description = row[col_indices['description']].strip()
            if not description:
                return None
            
            # Extract amount
            amount_str = None
            transaction_type = "debit"
            
            if 'amount' in col_indices:
                amount_str = row[col_indices['amount']].strip()
                # Detect CR/DR suffix to determine type
                if 'CR' in amount_str.upper():
                    transaction_type = "credit"
            elif 'debit' in col_indices:
                amount_str = row[col_indices['debit']].strip()
                transaction_type = "debit"
            elif 'credit' in col_indices:
                amount_str = row[col_indices['credit']].strip()
                transaction_type = "credit"
            
            if not amount_str or amount_str in ['', '-', 'N/A']:
                return None
            
            # Create Transaction object (Pydantic will validate)
            transaction = Transaction(
                date=self._parse_date(date_str),
                merchant=description,
                amount=self._parse_amount(amount_str),
                transaction_type=transaction_type,
                description=description
            )
            
            return transaction
            
        except Exception as e:
            print(f"Error parsing row {row}: {e}")
            return None
    
    def _extract_from_text(self, text_lines: List[Dict]) -> List[Transaction]:
        """Extract transactions from unstructured text"""
        transactions = []
        
        # Amazon PDF format: DD/MM/YYYY SerNo Merchant RewardPts Amount
        # Example: 16/01/2023 7075427598 KOTTARAM BAKES KOTTAYAM IN 8 850.00
        # Amount is ALWAYS the last number on the line (rightmost)
        amazon_pattern = re.compile(
            r'(\d{2}/\d{2}/\d{4})\s+'  # Date DD/MM/YYYY
            r'(\d+)\s+'  # SerNo (transaction ID)
            r'(.+?)\s+'  # Merchant name (non-greedy)
            r'(\d+)\s+'  # Reward points (CAPTURE!)
            r'([\d,]+\.\d{2})\s*$',  # Amount at end of line (must have .XX decimals)
            re.IGNORECASE
        )
        
        # Generic fallback pattern
        generic_pattern = re.compile(
            r'(\d{2}[/-]\d{2}[/-]\d{4}|\d{2}\s+\w{3}\s+\d{4})\s+'  # Date
            r'(.+?)\s+'  # Description
            r'([\d,]+\.?\d{0,2})\s*'  # Amount
            r'(Cr|Dr|CR|DR)?',  # Optional credit/debit marker
            re.IGNORECASE
        )
        
        for line_data in text_lines:
            text = line_data.get('text', '')
            
            # Try Amazon format first
            matches = list(amazon_pattern.finditer(text))
            for match in matches:
                try:
                    date_str = match.group(1)
                    # Group 2 is SerNo, skip it
                    description = match.group(3).strip()
                    reward_pts = int(match.group(4))
                    amount_str = match.group(5)
                    
                    # Amazon format doesn't have CR/DR suffix in this pattern
                    txn_type = "debit"  # Default for purchases
                    
                    transaction = Transaction(
                        date=self._parse_date(date_str),
                        merchant=description,
                        amount=self._parse_amount(amount_str),
                        reward_points=reward_pts,
                        transaction_type=txn_type,
                        description=description
                    )
                    
                    transactions.append(transaction)
                    
                except Exception as e:
                    continue
            
            # If no Amazon format matches, try generic
            if not matches:
                matches = list(generic_pattern.finditer(text))
            for match in matches:
                try:
                    date_str = match.group(1)
                    description = match.group(2).strip()
                    amount_str = match.group(3)
                    txn_type_marker = match.group(4)
                    
                    txn_type = "credit" if txn_type_marker and 'cr' in txn_type_marker.lower() else "debit"
                    
                    transaction = Transaction(
                        date=self._parse_date(date_str),
                        merchant=description,
                        amount=self._parse_amount(amount_str),
                        transaction_type=txn_type,
                        description=description
                    )
                    
                    transactions.append(transaction)
                    
                except Exception as e:
                    continue
        
        return transactions
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date from various formats"""
        # Try common formats
        formats = [
            '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d',
            '%d-%m-%Y', '%d %b %Y', '%d %B %Y',
            '%b %d, %Y', '%B %d, %Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse date: {date_str}")
    
    def _parse_amount(self, amount_str: str) -> Decimal:
        """Parse amount from string, handling CR/DR suffixes"""
        # Remove currency symbols, commas, and CR/DR markers
        cleaned = amount_str.replace('$', '').replace('₹', '').replace(',', '').strip()
        cleaned = cleaned.replace('CR', '').replace('Dr', '').replace('DR', '').strip()
        
        # Handle empty or invalid strings
        if not cleaned or cleaned == '-':
            raise ValueError(f"Invalid amount: {amount_str}")
        
        return Decimal(cleaned)
    
    def _classify_with_llm(self, transactions: List[Transaction]) -> List[Transaction]:
        """
        Use LLM to classify transactions into categories.
        """
        if not self.llm:
            return transactions
        
        # Batch transactions for efficiency (process 5 at a time)
        batch_size = 5
        
        prompt = ChatPromptTemplate.from_template(
            """Classify the following credit card transactions into categories.

Transactions:
{transactions}

For each transaction, determine the category from:
- Groceries
- Dining
- Fuel
- Shopping
- Entertainment
- Travel
- Utilities
- Healthcare
- Education
- Other

Respond with a JSON array ONLY (no other text):
[
  {{"merchant": "merchant_name", "category": "category_name"}},
  ...
]"""
        )
        
        for i in range(0, len(transactions), batch_size):
            batch = transactions[i:i+batch_size]
            
            # Format transactions for prompt
            txn_text = "\n".join([
                f"{idx+1}. {txn.merchant} - INR {txn.amount}"
                for idx, txn in enumerate(batch)
            ])
            
            try:
                response = self.llm.invoke(
                    prompt.format(transactions=txn_text)
                )
                
                # Parse LLM response
                content = response.content.strip()
                # Remove markdown code blocks if present
                if content.startswith('```'):
                    content = '\n'.join(content.split('\n')[1:-1])
                
                classifications = json.loads(content)
                
                # Apply classifications
                for txn, classification in zip(batch, classifications):
                    if isinstance(classification, dict) and 'category' in classification:
                        txn.category = classification['category']
                        print(f"  [OK] {txn.merchant[:30]:30s} -> {txn.category}")
                
            except json.JSONDecodeError as e:
                print(f"  [WARN] Failed to parse LLM response: {e}")
                print(f"  [WARN] Response was: {response.content[:200]}")
                continue
            except Exception as e:
                print(f"  [WARN] LLM classification failed: {e}")
                continue
        
        return transactions
    
    def validate_categories_with_second_llm(self, transactions: List[Transaction]) -> Dict:
        """
        Validate transaction categories using a second LLM model.
        Returns comparison results showing original vs validation categories.
        """
        if not self.llm:
            return {"status": "skipped", "reason": "LLM not available"}
        
        # Use different model for validation - try multiple models
        validation_models = [
            "llama-3.1-8b-instant",  # Use fast model for validation now
            "llama-3.3-70b-versatile"  # Fallback to same if needed
        ]
        
        validation_llm = None
        validation_model = None
        
        for model in validation_models:
            try:
                validation_llm = ChatGroq(
                    model=model,
                    temperature=0.0,  # More deterministic for validation
                    groq_api_key=config.groq_api_key
                )
                validation_model = model
                print(f"\n=> Validating with second LLM ({validation_model})...")
                print(f"=> Total transactions to validate: {len(transactions)}")
                break
            except Exception as e:
                continue
        
        if not validation_llm:
            return {"status": "error", "reason": "No working validation models available"}
        
        # Batch validation
        batch_size = 5
        comparison_results = []
        matches = 0
        mismatches = 0
        
        prompt = ChatPromptTemplate.from_template(
            """Classify the following credit card transactions into categories.

Transactions:
{transactions}

For each transaction, determine the category from:
- Groceries
- Dining
- Fuel
- Shopping
- Entertainment
- Travel
- Utilities
- Healthcare
- Education
- Other

Respond with a JSON array ONLY (no other text):
[
  {{"merchant": "merchant_name", "category": "category_name"}},
  ...
]"""
        )
        
        for i in range(0, len(transactions), batch_size):
            batch = transactions[i:i+batch_size]
            
            # Format transactions for prompt
            txn_text = "\n".join([
                f"{idx+1}. {txn.merchant} - INR {txn.amount}"
                for idx, txn in enumerate(batch)
            ])
            
            try:
                response = validation_llm.invoke(
                    prompt.format(transactions=txn_text)
                )
                
                # Parse LLM response
                content = response.content.strip()
                if content.startswith('```'):
                    content = '\n'.join(content.split('\n')[1:-1])
                
                validations = json.loads(content)
                
                # Ensure we only process the same number of validations as transactions in batch
                if len(validations) != len(batch):
                    print(f"  [WARN] Validation returned {len(validations)} results for {len(batch)} transactions - truncating")
                    validations = validations[:len(batch)]
                
                # Compare with original categories
                for txn, validation in zip(batch, validations):
                    if isinstance(validation, dict) and 'category' in validation:
                        original_cat = txn.category
                        validated_cat = validation['category']
                        
                        match = original_cat == validated_cat
                        if match:
                            matches += 1
                            status = "[OK]"
                        else:
                            mismatches += 1
                            status = "[DIFF]"
                        
                        comparison_results.append({
                            'merchant': txn.merchant,
                            'original_category': original_cat,
                            'validated_category': validated_cat,
                            'match': match
                        })
                        
                        print(f"  {status} {txn.merchant[:35]:35s} | {original_cat:15s} vs {validated_cat:15s}")
                
            except json.JSONDecodeError as e:
                print(f"  [WARN] Failed to parse validation response: {e}")
                continue
            except Exception as e:
                print(f"  [WARN] Validation failed for batch: {e}")
                continue
        
        total = matches + mismatches
        accuracy = (matches / total * 100) if total > 0 else 0
        
        print(f"\n=> Validation complete: {matches} matches, {mismatches} mismatches, {total} total ({accuracy:.2f}% accuracy)")
        
        return {
            'status': 'completed',
            'validation_model': validation_model,
            'total_transactions': total,
            'matches': matches,
            'mismatches': mismatches,
            'accuracy_percent': accuracy,
            'comparisons': comparison_results
        }
    
    def extract_card_metadata(self, parsed_data: Dict) -> Optional[CardMetadata]:
        """Extract credit card metadata from parsed data"""
        key_value_pairs = parsed_data.get('key_value_pairs', {})
        text_lines = parsed_data.get('text_lines', [])
        
        # Combine all text for pattern matching
        all_text = ' '.join([line.get('text', '') for line in text_lines])
        
        # Extract card number (last 4 digits)
        card_pattern = re.search(r'(?:card.*?ending|ending\s+in|last\s+4\s+digits?)[:\s]*(\d{4})', all_text, re.IGNORECASE)
        last_four = card_pattern.group(1) if card_pattern else "0000"
        
        # Extract issuer
        issuer = self._extract_issuer(all_text, key_value_pairs)
        
        # Extract card type
        card_type = self._extract_card_type(all_text)
        
        try:
            metadata = CardMetadata(
                issuer=issuer or "Unknown Bank",
                card_type=card_type or "Credit Card",
                card_product="Unknown Product",
                last_four_digits=last_four
            )
            return metadata
        except Exception as e:
            print(f"[WARN] Could not create card metadata: {e}")
            return None
    
    def _extract_issuer(self, text: str, key_values: Dict) -> Optional[str]:
        """Extract bank/issuer name"""
        # Common bank names
        banks = [
            'Chase', 'American Express', 'Amex', 'Citibank', 'Citi',
            'Capital One', 'Discover', 'Bank of America', 'Wells Fargo',
            'HDFC', 'ICICI', 'SBI', 'Axis Bank'
        ]
        
        text_lower = text.lower()
        for bank in banks:
            if bank.lower() in text_lower:
                return bank
        
        return None
    
    def _extract_card_type(self, text: str) -> Optional[str]:
        """Extract card network type"""
        text_lower = text.lower()
        
        if 'visa' in text_lower:
            return 'Visa'
        elif 'mastercard' in text_lower or 'master card' in text_lower:
            return 'Mastercard'
        elif 'american express' in text_lower or 'amex' in text_lower:
            return 'American Express'
        elif 'discover' in text_lower:
            return 'Discover'
        
        return 'Credit Card'
    
    def extract_reward_points(self, parsed_data: Dict) -> RewardPoints:
        """Extract reward points information"""
        key_value_pairs = parsed_data.get('key_value_pairs', {})
        text_lines = parsed_data.get('text_lines', [])
        
        all_text = ' '.join([line.get('text', '') for line in text_lines])
        
        # Patterns for reward points
        points_earned_pattern = re.search(r'(?:points?\s+earned|earned\s+points?)[:\s]*([\d,]+)', all_text, re.IGNORECASE)
        points_balance_pattern = re.search(r'(?:points?\s+balance|available\s+points?)[:\s]*([\d,]+)', all_text, re.IGNORECASE)
        
        rewards = RewardPoints(
            points_earned=Decimal(points_earned_pattern.group(1).replace(',', '')) if points_earned_pattern else Decimal("0"),
            points_balance=Decimal(points_balance_pattern.group(1).replace(',', '')) if points_balance_pattern else Decimal("0")
        )
        
        return rewards
