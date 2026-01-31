"""
FastAPI REST API for PDF Transaction Parser
Provides endpoints for PDF parsing and transaction retrieval
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Optional
import json
import shutil
from datetime import datetime

from src.parser_service import PDFParserService
from src.transaction_extractor import TransactionExtractor

# Initialize FastAPI app
app = FastAPI(
    title="Credit Card Transaction Parser API",
    description="API for parsing credit card statements and extracting transactions",
    version="1.0.0"
)

# Security
security = HTTPBearer()

# Static token configuration
VALID_TOKENS = {
    "cc_user1_token_2026": "CCUser1"  # token: username
}

# Initialize parser
parser = PDFParserService()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify bearer token and return username"""
    token = credentials.credentials
    
    if token not in VALID_TOKENS:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )
    
    return VALID_TOKENS[token]


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "service": "Credit Card Transaction Parser API",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "GET /health": "Health check",
            "POST /api/v1/parse-pdf": "Upload and parse PDF (requires authentication)",
            "GET /api/v1/transactions": "Get latest transaction summary (requires authentication)",
            "GET /api/v1/categories": "Get spending by category (requires authentication)"
        },
        "authentication": "Bearer token required in Authorization header"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "pdf-parser-api"
    }


@app.post("/api/v1/parse-pdf")
async def parse_pdf(
    file: UploadFile = File(...),
    validate: bool = False,
    username: str = Depends(verify_token)
):
    """
    Upload and parse a credit card statement PDF
    
    Args:
        file: PDF file to parse
        validate: If True, validate classifications with second LLM model (slower but more accurate)
        username: Authenticated username from token
    
    Returns:
        Parsed transactions with categorization
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    # Save uploaded file temporarily
    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    
    temp_file_path = temp_dir / file.filename
    
    try:
        # Save uploaded file
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Parse PDF
        result = parser.parse_statement(str(temp_file_path))
        
        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=f"PDF parsing failed: {result.error_message}"
            )
        
        # Optionally validate categories with second LLM
        validation_result = None
        if validate:
            extractor = TransactionExtractor()
            validation_result = extractor.validate_categories_with_second_llm(result.statement_data.transactions)
        
        # Extract transactions (only debits)
        transactions = [
            txn for txn in result.statement_data.transactions 
            if txn.transaction_type == 'debit'
        ]
        
        # Build response
        from decimal import Decimal
        from collections import defaultdict
        from src.config import config
        
        category_summary = defaultdict(lambda: {
            'money_spent': Decimal('0'),
            'rewards_earned': 0,
            'transaction_count': 0,
            'transactions': []
        })
        
        for txn in transactions:
            category = txn.category or 'Uncategorized'
            
            category_summary[category]['money_spent'] += txn.amount
            category_summary[category]['rewards_earned'] += (txn.reward_points or 0)
            category_summary[category]['transaction_count'] += 1
            
            category_summary[category]['transactions'].append({
                'date': txn.date.strftime('%Y-%m-%d'),
                'merchant': txn.merchant,
                'amount': float(txn.amount),
                'reward_points': txn.reward_points or 0
            })
        
        # Build final response
        response_data = {
            'username': username,
            'parsed_at': datetime.now().isoformat(),
            'summary': {
                'total_categories': len(category_summary),
                'total_transactions': len(transactions),
                'total_spending': float(sum(cat['money_spent'] for cat in category_summary.values())),
                'total_rewards': sum(cat['rewards_earned'] for cat in category_summary.values()),
                'source_file': file.filename
            },
            'categories': {}
        }
        
        # Add model info if validation was performed
        if validate and validation_result:
            response_data['model_info'] = {
                'primary_model': config.groq_model,
                'validation_model': validation_result.get('validation_model', 'llama-3.1-8b-instant'),
                'accuracy': validation_result.get('accuracy', 0),
                'matches': validation_result.get('matches', 0),
                'total_transactions': validation_result.get('total', 0),
                'validation_enabled': True
            }
        else:
            response_data['model_info'] = {
                'primary_model': config.groq_model,
                'validation_enabled': False
            }
        
        # Add category details
        for category, data in sorted(category_summary.items()):
            response_data['categories'][category] = {
                'classification_type': category,
                'money_spent': float(data['money_spent']),
                'rewards_earned': data['rewards_earned'],
                'transaction_count': data['transaction_count'],
                'transactions': data['transactions']
            }
        
        # Save to output for GET endpoint
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "transactions_summary.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, indent=2, ensure_ascii=False)
        
        return response_data
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )
    finally:
        # Cleanup temp file
        if temp_file_path.exists():
            temp_file_path.unlink()


@app.get("/api/v1/transactions")
async def get_transactions(username: str = Depends(verify_token)):
    """
    Get latest transaction summary
    
    Args:
        username: Authenticated username from token
    
    Returns:
        Latest transaction summary from stored JSON
    """
    output_path = Path("output/transactions_summary.json")
    
    if not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No transaction data found. Please parse a PDF first using POST /api/v1/parse-pdf"
        )
    
    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Add request metadata
        data['requested_by'] = username
        data['retrieved_at'] = datetime.now().isoformat()
        
        return data
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading transaction data: {str(e)}"
        )


@app.get("/api/v1/categories")
async def get_categories(username: str = Depends(verify_token)):
    """
    Get spending summary by category (without individual transaction details)
    
    Args:
        username: Authenticated username from token
    
    Returns:
        Lightweight category-wise spending summary (no transaction details)
    """
    output_path = Path("output/transactions_summary.json")
    
    if not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No transaction data found. Please parse a PDF first."
        )
    
    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract categories WITHOUT individual transactions (lightweight)
        categories_summary = {}
        for category_name, category_data in data.get('categories', {}).items():
            categories_summary[category_name] = {
                'classification_type': category_data.get('classification_type'),
                'money_spent': category_data.get('money_spent'),
                'rewards_earned': category_data.get('rewards_earned'),
                'transaction_count': category_data.get('transaction_count')
                # Exclude 'transactions' array for lighter payload
            }
        
        return {
            'username': username,
            'retrieved_at': datetime.now().isoformat(),
            'summary': data.get('summary', {}),
            'categories': categories_summary
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading category data: {str(e)}"
        )


@app.get("/api/v1/categories/{category_name}")
async def get_category_details(
    category_name: str,
    username: str = Depends(verify_token)
):
    """
    Get detailed transactions for a specific category
    
    Args:
        category_name: Name of category (Groceries, Dining, etc.)
        username: Authenticated username from token
    
    Returns:
        Detailed transactions for the specified category
    """
    output_path = Path("output/transactions_summary.json")
    
    if not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No transaction data found"
        )
    
    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        categories = data.get('categories', {})
        
        if category_name not in categories:
            raise HTTPException(
                status_code=404,
                detail=f"Category '{category_name}' not found. Available: {', '.join(categories.keys())}"
            )
        
        return {
            'username': username,
            'category': category_name,
            'data': categories[category_name]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading category data: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    
    print("="*60)
    print("Credit Card Transaction Parser API")
    print("="*60)
    print("\nAuthentication Token: cc_user1_token_2026")
    print("Username: CCUser1")
    print("\nStarting server on http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("="*60)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
