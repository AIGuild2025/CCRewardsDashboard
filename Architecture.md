# Credit Card Reward Intelligence Dashboard

## 1. Purpose

This document describes the high-level and low-level architecture for the **Credit Card Reward Intelligence Dashboard**, a hackathon project designed to aggregate credit card rewards, parse statements, and provide AI-powered recommendations using RAG (Retrieval-Augmented Generation).

The goal of this architecture is to be:

* **Hackathon-friendly** (fast to build, demo-ready)
* **Scalable** (extensible to more banks, cards, and features)
* **Secure** (handles financial data and PII responsibly)

---

## 2. System Overview

The system enables users to:

* Upload credit card statements (PDF / Email)
* View consolidated reward points across cards
* Ask natural language questions about rewards & benefits
* Get optimal redemption recommendations powered by AI

### High-Level Flow

```
User
  ↓
Frontend (Web Dashboard + AI Chat)
  ↓
API Gateway
  ↓
Backend Services
  ├─ Statement Parser Service
  ├─ Reward Knowledge (RAG) Service
  ├─ Recommendation Engine
  ↓
Data Stores (SQL, Vector DB, Object Storage)
```

---

## 3. High-Level Architecture

### 3.1 Frontend Layer

**Tech Stack**:

* React / Next.js
* Tailwind / Material UI (optional)
* Chat UI for AI interactions

**Responsibilities**:

* User authentication (basic for MVP)
* Statement upload (PDF)
* Dashboard visualization (points, value, trends)
* Chat-based Q&A for rewards and benefits

---

### 3.2 API Gateway

Acts as a single entry point for all frontend requests.

**Responsibilities**:

* Request routing
* Authentication & authorization
* Rate limiting (optional for MVP)
* API versioning

**Examples**:

* `/upload-statement`
* `/rewards/summary`
* `/chat/query`
* `/recommendations`

---

## 4. Backend Services

### 4.1 Statement Parser Service

**Purpose**:
Convert raw statements into structured transaction and reward data with high accuracy (target: 95%+ for real-world PDFs).

**Input**:

* PDF statements (multiple bank formats)
* Email statements (future)

**Processing Steps**:

1. **Document Ingestion** (Secure upload to S3)
   * File validation (PDF format check, file size limits)
   * Virus scanning (ClamAV or similar)
   * Encryption before storage

2. **Advanced PDF Parsing** (Infrastructure-specific)
   * **Primary Tool**: AWS Textract OR Azure Document Intelligence
   * **Fallback**: Unstructured.io (local parsing)
   * Handles complex layouts: multi-column, images, tables, varied fonts
   * Extracts: Transaction rows, reward points, balances, dates
   
3. **Pattern-based + LLM-assisted Extraction**
   * Rule-based extraction for high-confidence fields (transaction amount, date)
   * LLM refinement for ambiguous fields (merchant category, reward earning rule)
   * Orchestrated via **LangChain** for workflow management

4. **PII Masking** (See Security section 6.1)
   * Remove/tokenize sensitive information before storage
   * Maintain anonymized transaction history

5. **Data Normalization**
   * Convert to standardized JSON schema
   * Validate against schema (missing fields, data type mismatches)

**Output**:

* Transactions (date, merchant, amount, category, anonymized)
* Monthly reward points earned
* Card metadata (issuer, card type, last 4 digits)

**Technology Stack**:

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| PDF Parsing | **AWS Textract** (primary) or **Azure Document Intelligence** | Handles complex real-world bank statement layouts; handles tables and multi-column formats |
| Fallback Parser | **Unstructured.io** | Open-source, runs locally if cloud parsing fails |
| LLM Orchestration | **LangChain** with **Claude 3.5 Sonnet** or **GPT-4o** | Chains PDF extraction → field validation → LLM refinement |
| Validation | **Pydantic** (Python) | Schema validation, type safety |
| Storage | **S3** (raw PDFs) + **PostgreSQL** (extracted data) | Encrypted storage with audit logs |

---

### 4.2 Reward Knowledge Service (RAG)

**Purpose**:
Provide accurate, contextual answers about credit card benefits, rules, and redemption options while ensuring factual correctness through continuous evaluation.

#### RAG Pipeline

**Ingestion Sources**:

* Bank websites (HTML/PDF)
* Card benefit documents
* Third-party comparison portals

**Embedding & Storage**:

* Chunk size: 1024 tokens
* Embedding models:
  * `text-embedding-3-large`
* Stored in Vector Database with metadata

**Retrieval & Generation**:

1. User query embedding
2. Vector similarity search
3. Context assembly
4. LLM response generation

#### 4.2.1 Evaluation Framework (DeepEval)

**Problem**: Without continuous evaluation, the RAG pipeline risks hallucinating incorrect financial advice, which could lead to poor user decisions and loss of trust.

**Why DeepEval?**
DeepEval is superior to RAGAS/TruLens for this financial domain because:
- **LLM-as-judge flexibility**: G-Eval metric allows custom domain-specific criteria (e.g., "verify reward earning rates against bank documentation")
- **Non-intrusive tracing**: `@observe` decorator for component-level evaluation without code rewrites
- **Confident AI platform**: Built-in cloud dashboard for iteration comparison, dataset curation, and production monitoring
- **Financial-grade RAG metrics**: All RAG metrics (faithfulness, relevance, precision) + custom fact verification
- **Active development**: 13k+ GitHub stars, 229 contributors, latest release Dec 2025

**Evaluation Metrics** (DeepEval):

1. **Faithfulness** (Does the response stay true to source documents?)
   * Tool: DeepEval `FaithfulnessMetric`
   * Target: >90% (penalizes made-up facts)
   * Example: If source says "5x points on flights," answer must not claim "10x points"

2. **Answer Relevance** (Does the response directly answer the user's question?)
   * Tool: DeepEval `AnswerRelevancyMetric`
   * Target: >85%
   * Example: Query "best card for dining" should not primarily discuss travel benefits

3. **Contextual Precision** (Is retrieved context actually needed for the answer?)
   * Tool: DeepEval `ContextualPrecisionMetric`
   * Target: >80% (removes unnecessary context)
   * Example: Don't retrieve entire card glossary if only annual fee is relevant

4. **Financial Claim Accuracy** (Domain-specific custom evaluation)
   * Tool: DeepEval `GEval` (LLM-as-judge with custom criteria)
   * Target: >95% (highest standard for financial accuracy)
   * Implementation: "Verify that reward earning rates, annual fees, and benefits exactly match official bank documentation. Flag any discrepancies."

5. **Hallucination Detection** (Are specific financial claims verifiable?)
   * Tool: DeepEval `HallucinationMetric`
   * Target: <5% hallucination rate
   * Implementation: Fact-check numerical claims (reward rates, annual fees) against source documents

**DeepEval Implementation Example**:

```python
from deepeval import evaluate
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    GEval,
    HallucinationMetric
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.tracing import observe, update_current_span

# Define custom financial accuracy metric
financial_accuracy = GEval(
    name="Financial Claim Accuracy",
    criteria="Verify that reward earning rates, annual fees, and benefits stated in the response "
             "exactly match official bank documentation. Flag any invented or inaccurate claims. "
             "Example: If Chase Sapphire docs say '5x points on flights', accept only that rate.",
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.RETRIEVAL_CONTEXT],
    threshold=0.95
)

# Standard RAG metrics
faithfulness = FaithfulnessMetric(threshold=0.90)
answer_relevancy = AnswerRelevancyMetric(threshold=0.85)
context_precision = ContextualPrecisionMetric(threshold=0.80)
hallucination = HallucinationMetric(threshold=0.95)  # <5% hallucination

# Component-level tracing (non-intrusive)
@observe(metrics=[faithfulness, answer_relevancy, context_precision])
def retrieve_card_benefits(card_name: str) -> str:
    # Your retriever code here
    context = vector_db.similarity_search(f"benefits for {card_name}")
    return context

@observe(metrics=[financial_accuracy, hallucination])
def generate_recommendation(user_query: str, retrieval_context: str) -> str:
    # Your LLM call here
    response = llm.generate(prompt=f"{user_query}\\n\\nContext: {retrieval_context}")
    update_current_span(test_case=LLMTestCase(
        input=user_query,
        actual_output=response,
        retrieval_context=retrieval_context
    ))
    return response

# Evaluate test case
test_case = LLMTestCase(
    input="Is Chase Sapphire Preferred good for airline purchases?",
    actual_output="Yes, Chase Sapphire Preferred earns 5x points on flights and hotels.",
    retrieval_context="Chase Sapphire Preferred: Earn 5x points per $1 on flights and hotels..."
)

evaluate([test_case], [financial_accuracy, faithfulness, answer_relevancy, hallucination])
```

**Evaluation Workflow**:

```
User Query
  ↓
RAG Pipeline (Generation) with @observe decorator
  ↓
DeepEval Metrics Suite
  ├─ Faithfulness: Response matches source docs
  ├─ Answer Relevancy: Response answers user question
  ├─ Context Precision: Retrieved context is minimal & sufficient
  ├─ Financial Accuracy (G-Eval): Custom financial claim verification
  └─ Hallucination: Detect invented facts
  ↓
Logging & Monitoring (via Confident AI platform)
  ├─ Store low-scoring answers in fallback DB
  ├─ Dashboard: Evaluation metrics trending (real-time)
  └─ Alert: If score < threshold or 10+ hallucinations/day detected
  ↓
Feedback Loop
  ├─ Human expert reviews flagged responses (Phase 4)
  ├─ Adjust retriever (chunk size, metadata filters)
  ├─ Retrain embeddings if corpus changed
  ├─ Update LLM prompt based on correction patterns
  └─ Compare iterations on Confident AI platform
```

**Production Deployment**:

* **Weekly evaluation runs**: 100 historical queries to detect drift
* **Real-time evaluation**: 10% of production queries (sampled)
* **Alerts**: If average Financial Accuracy score drops below 93% or Faithfulness <88%
* **Dashboard**: Confident AI platform displays all metrics in real-time
* **Quarterly manual audit**: High-impact recommendations reviewed by domain experts
* **Iteration comparison**: A/B test new retrievers/prompts on Confident AI platform

#### 4.2.2 Orchestration Framework (LangChain / LlamaIndex)

**Purpose**: Manage complex RAG workflows including document chunking, embedding, retrieval, and LLM generation in a maintainable, reproducible manner.

**Technology Stack**:

| Component | Tool | Rationale |
|-----------|------|-----------|
| **LLM Orchestration** | **LangChain** | Largest ecosystem, strong RAG support, production-ready |
| **LLM Provider** | **Claude 3.5 Sonnet** or **GPT-4o** | Strong reasoning for financial context, accurate knowledge cutoff |
| **Embedding Model** | **text-embedding-3-large** (retrieval) + **text-embedding-3-small** (caching) | Superior semantic understanding; cost-effective dual approach |
| **Document Indexing** | **LangChain Document Loaders** + **RecursiveCharacterTextSplitter** | Handles HTML, PDF, Markdown; smart chunk overlap |
| **Memory Management** | **LangChain ConversationBufferMemory** | Maintains chat history for multi-turn queries |
| **Retrieval Strategy** | **Hybrid Search** (Dense + Sparse) | Combines semantic (vector) + keyword (BM25) search for financial specificity |

**Workflow Example** (LangChain):

```python
from langchain.chains import RetrievalQA
from langchain.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Pinecone
from langchain.llms import ChatOpenAI

# 1. Load benefit documents
loader = WebBaseLoader(url="bank-benefits-page.html")
documents = loader.load()

# 2. Chunk intelligently
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1024,
    chunk_overlap=100,
    separators=["\n\n", "\n", " "]
)
chunks = splitter.split_documents(documents)

# 3. Embed & store
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
vector_db = Pinecone.from_documents(chunks, embeddings)

# 4. Orchestrate RAG
llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=vector_db.as_retriever(search_kwargs={"k": 5}),
    chain_type="stuff"  # or "map_reduce" for longer contexts
)

# 5. Query
response = qa_chain.run("What's the best way to use my Sapphire points?")
```

**Production Considerations**:

* **Prompt versioning**: Track prompts in version control (important for reproducibility)
* **Chain composition**: Use `Runnable` interface for modular, testable chains
* **Error handling**: Fallback to cached responses or clarification prompts on LLM failures
* **Monitoring**: Log all LLM calls for cost tracking and hallucination detection

---

### 4.3 Caching Layer (Semantic Cache)

**Purpose**:
Reduce LLM token costs and improve response latency by caching common queries and their results.

**Problem**: Identical or semantically similar queries (e.g., "best airline card" vs. "which card for flights?") currently trigger redundant LLM calls, incurring unnecessary costs and latency.

**Solution**: Semantic Caching with Redis

```
User Query
  ↓
Query Embedding (lightweight embedding model)
  ↓
Semantic Cache Lookup
  ├─ If similarity > threshold (0.95), return cached result
  └─ If no match, proceed to RAG pipeline
  ↓
Cache Store (Redis with TTL)
  ├─ Key: query_embedding + hash
  ├─ Value: {response, retrieval_context, timestamp}
  └─ TTL: 7 days (reward rates stable) OR 24h (dynamic benefits)
```

**Implementation Details**:

1. **Cache Invalidation Strategy**:
   * **Manual**: When reward rates or bank benefits are updated
   * **Time-based**: 7-day TTL for stable data (annual fees), 24h for promotions
   * **Event-based**: On new card launch, rate change detected

2. **Cost Reduction Estimate** (Assuming 1000 queries/day):
   * Without cache: 1000 LLM calls × $0.005 = **$5/day** (~$150/month)
   * With cache (60% hit rate): 400 LLM calls × $0.005 = **$2/day** (~$60/month)
   * **Monthly savings: ~$90** (40% reduction)

3. **Technology Stack**:
   * **Redis** (in-memory store): Fast semantic lookup
   * **Embedding model**: `text-embedding-3-small` (faster, cheaper than 3-large)
   * **Client**: Redis Python (redis-py) or LangChain's `UpstashRedisCache`

4. **Metrics to Monitor**:
   * Cache hit rate (target: >50%)
   * Average response time (cached vs. uncached)
   * Memory usage in Redis

---

### 4.4 Recommendation Engine

**Purpose**:
Suggest optimal reward usage based on:

* Current reward balance
* Expiry timelines
* Transfer ratios
* User preferences (future)

**Examples**:

* Best airline / hotel transfer
* Cashback vs travel redemption
* Expiring points alerts

**Logic**:

* Rule-based logic (MVP)
* ML-based ranking (future)

---

---

## 7. Real-World Data Strategy

### 7.1 Problem Statement

Production systems trained on a single bank's statement format will fail when users upload statements from other issuers. Real-world bank PDFs vary wildly in:
- Layout (single-column vs. multi-column, header/footer styles)
- Terminology (e.g., "Points Earned" vs. "Rewards Posted" vs. "Bonus Points")
- Tables & structure (some have summary sections, others inline)
- Fonts, colors, and OCR difficulty

### 7.2 Data Diversity & Acquisition Strategy

**Phase 1: Multi-Bank Coverage (MVP)**
- **Target banks**: HDFC, ICICI, SBI
- **Acquisition method**:
  1. **Community crowdsourcing**: Solicit anonymized statements from users (with PII removal consent)
  2. **Test accounts**: Create test accounts with partner banks, generate sample statements
  3. **Public resources**: Scrape bank websites for sample benefit PDFs, annual reports
  4. **Financial data APIs**: Purchase sample data from financial aggregators (e.g., Plaid test datasets)

**Phase 2: Data Validation**
- **Quality assurance**: Manual spot-check for PII leakage before storage
- **Diversity metrics**: Track statement count by bank, vintage (card product maturity)
- **Coverage goal**: 500+ real statements across 6+ banks by Phase 2 completion

**Sample statement dataset structure**:
```
data/
  ├── statements/
  │   ├── chase/
  │   │   ├── sapphire_preferred_001.pdf
  │   │   ├── freedom_unlimited_002.pdf
  │   │   └── ...
  │   ├── amex/
  │   │   ├── platinum_001.pdf
  │   │   └── ...
  │   └── ...
  └── metadata.csv
      # bank, card_product, date_range, statement_count
```

### 7.3 Dynamic Data Ingestion (Web Scraping & APIs)

**Purpose**: Keep card benefit information fresh without manual updates.

**Challenge**: Bank websites often employ anti-scraping measures (JavaScript rendering, rate limiting, IP blocking).

**Solution Stack**:

| Component | Technology | Use Case |
|-----------|-----------|----------|
| **Headless Browser** | **Selenium** or **Playwright** | Navigate dynamic JS-heavy bank sites |
| **Rate Limiting** | **Scrapy** with `DOWNLOAD_DELAY` | Respect robots.txt, avoid IP bans |
| **Data Aggregation API** (Preferred) | **Plaid**, **Salt Edge**, or **Open Banking APIs** | Compliant, structured access to account & rewards data |
| **Fallback Scraping** | **BeautifulSoup** + **Requests** | Simple HTML parsing for static benefit pages |

**Workflow** (Plaid API example):

```
Bank Benefit Pages (Bank Websites)
  ↓
Plaid API / Open Banking (PSD2 EU / Open Banking UK)
  ├─ Account structure (if user consents)
  ├─ Transaction data
  └─ Rewards metadata
  ↓
Transformation Service
  ├─ Normalize field names
  ├─ Enrich with missing metadata
  └─ Store in Vector DB with timestamps
  ↓
Daily Scheduled Job (Airflow)
  ├─ Detect reward rate changes
  ├─ Alert on new card launches
  └─ Update vector embeddings
```

**Compliance**:
- **Terms of Service**: Use official APIs where available (Plaid, Salt Edge)
- **robots.txt**: Respect crawl delays
- **Legal**: Consult with legal on scraping if necessary (usually lower risk for public benefit pages)
- **User consent**: Only scrape/aggregate with explicit user permission for their account data

### 7.4 Metadata Enrichment Strategy

**Current Gap**: The architecture mentions "metadata" but doesn't define it systematically.

**Proposed Metadata Schema** (for every chunk in Vector DB):

```json
{
  "chunk_id": "card_sapphire_pref_001",
  "text": "Earn 5x points on flights and hotels...",
  "metadata": {
    "bank_name": "Chase",
    "card_product_name": "Chase Sapphire Preferred",
    "card_tier": "Premium",
    "annual_fee": 95,
    "benefit_category": "Travel",
    "benefit_type": "Bonus Earning Rate",
    "applicable_merchants": ["airlines", "hotels"],
    "earning_rate": 5,
    "currency": "points",
    "source_url": "https://chase.com/benefits/...",
    "last_updated": "2025-01-14",
    "validity_period": "2024-01-01 to 2025-12-31",
    "is_promotional": false,
    "confidence_score": 0.98
  }
}
```

**Metadata Benefits**:

1. **Improved Retrieval** (Hybrid search):
   ```python
   # Filter by card tier while doing semantic search
   vector_db.similarity_search(
       query="best travel rewards",
       filter={"card_tier": {"$in": ["Premium", "Standard"]}}
   )
   ```

2. **Temporal Awareness**:
   ```python
   # Exclude expired promotions
   filter={"validity_period.end": {"$gte": datetime.now()}}
   ```

3. **Confidence-based Ranking**:
   ```python
   # Prioritize high-confidence sources
   results = sorted(results, key=lambda x: x.metadata["confidence_score"], reverse=True)
   ```

4. **Audit Trail**:
   - Track which sources were used for each recommendation
   - Explainability: "Based on official Chase documentation from Jan 2025"

**Data Pipeline for Metadata Collection**:

1. **Automated extraction**: LLM parses bank benefit pages, extracts structured metadata
2. **Validation**: Fact-check rates against multiple sources (Plaid, bank APIs)
3. **Manual review**: Quarterly audit by domain experts (1-2 hours/week)
4. **Versioning**: Keep historical metadata to detect changes

---

## 8. Tech Stack Summary

## 8. Tech Stack Summary

### 8.1 Complete Technology Selections

| Layer | Component | Technology | Rationale |
|-------|-----------|-----------|-----------|
| **Frontend** | Web Framework | Next.js + React | SSR, API routes, excellent DX |
| | UI Framework | Tailwind CSS + shadcn/ui | Rapid iteration, accessible components |
| | Chat UI | Vercel AI SDK or LangChain JS | Real-time streaming responses |
| **API** | Gateway | Express.js or FastAPI | Lightweight, well-supported |
| | Authentication | JWT + OAuth 2.0 | Stateless, scalable |
| | Rate Limiting | Redis-based (express-rate-limit) | Prevent abuse, cost control |
| **Backend Services** | Language | Python 3.11+ | ML/AI ecosystem, FastAPI speed |
| | PDF Parser | AWS Textract (primary) + Unstructured.io (fallback) | Production-grade layout handling |
| | LLM Orchestration | LangChain + Claude 3.5 Sonnet / GPT-4o | Production-grade orchestration |
| | Evaluation | **DeepEval** with G-Eval custom metrics | Domain-specific financial accuracy evaluation |
| | Evaluation Platform | **Confident AI** (cloud dashboard) | Iteration comparison, dataset curation, monitoring |
| | Semantic Cache | Redis + OpenAI Embeddings | Token cost reduction |
| **Data Layer** | SQL DB | PostgreSQL with pgvector | ACID compliance + vector support |
| | Vector DB | Pinecone or Weaviate | Managed embeddings, metadata filtering |
| | Object Storage | AWS S3 (with encryption) | Durable PDF storage |
| | Cache | Redis | Semantic cache, session store |
| **Data Pipelines** | Orchestration | Apache Airflow | Scheduled ingestion, monitoring |
| | Scraping | Plaid API (primary) + Playwright (fallback) | Compliant, dynamic content handling |
| **Monitoring** | Logging | ELK Stack or Datadog | Centralized observability |
| | Evaluation Dashboard | Grafana + Prometheus | Real-time metrics (cache hit rate, hallucinations) |
| | Budget Tracking | Custom dashboard (token costs, API spend) | ROI measurement |

---

## 9. Data Storage Layer (Detailed)

### 9.1 SQL Database

Stores structured, transactional data.

**Entities**:

* Users
* Credit Cards
* Transactions
* Reward Balances
* Evaluation logs (for DeepEval results: faithfulness, relevance, precision, hallucination scores)

**Examples**:

* PostgreSQL (with pgvector extension for vector operations)
* MySQL

---

### 9.2 Vector Database

Stores embedded credit card benefit documents with rich metadata.

**Examples**:

* Pinecone (fully managed, metadata filtering)
* Weaviate (open-source or cloud, flexible)
* Qdrant (high performance)

**Metadata Schema** (as defined in Section 7.4):
```json
{
  "bank_name": "Chase",
  "card_product_name": "Sapphire Preferred",
  "benefit_category": "Travel",
  "earning_rate": 5,
  "annual_fee": 95,
  "last_updated": "2025-01-14"
}
```

---

### 9.3 Object Storage

Stores raw documents and parsed outputs.

**Examples**:

* AWS S3
* GCP Cloud Storage
* Azure Blob Storage

**Contents**:

* PDF statements (encrypted, auto-deleted after 24h)
* Scraped HTML/PDF benefit docs
* Evaluation reports (flagged hallucinations)

---

## 10. Security Considerations (Detailed)

### 10.1 Data Security & PII Handling

**Problem**: Credit card statements contain sensitive Personal Identifiable Information (PII), including:
* Full names, addresses, phone numbers
* Credit card numbers (partially masked)
* Transaction histories
* Spending patterns

**Solution Architecture**:

1. **Data Masking/Anonymization Layer** (at Statement Parser Service)
   * Remove or hash PII before storing in Vector DB
   * Tokenize sensitive fields (card numbers → "****1234")
   * Timestamp anonymization (transactions → time ranges)
   * Pattern-based redaction for addresses and phone numbers

2. **Secure Data Flow**:
   ```
   Raw PDF (User Uploaded)
     ↓
   Secure File Upload (Encrypted S3 + ACL)
     ↓
   Parser Service (Runs in isolated container)
     ↓
   PII Masking Layer ← [Remove sensitive data]
     ↓
   Anonymized Extraction → Vector DB & SQL DB
   
   Raw PDF & Temporary Files → Auto-delete after 24 hours
   ```

3. **Storage Requirements**:
   * Encryption at rest (AES-256)
   * Encryption in transit (TLS 1.3)
   * Database-level encryption for SQL & Vector DB
   * Separate encryption keys for different data classes (user vs. transaction data)

4. **Access Control**:
   * Role-based access control (RBAC) for admin/service access
   * Token-based API authentication with short TTL (15 min for sensitive operations)
   * Audit logging for all PII-related queries
   * No long-term storage of raw credit card numbers or statements

### 10.2 Compliance & Standards
* GDPR: Right to be forgotten, data minimization
* CCPA: User consent tracking, data sale prohibition
* PCI-DSS: If handling card numbers directly (prefer indirect via masking)
* SOC 2: Regular security audits and pen tests

---

## 11. Phased Roadmap & Delivery Plan

The current "Future Enhancements" are features, not a delivery strategy. Below is a professional, phased roadmap with clear success criteria and ROI milestones.

### Phase 1: Data Acquisition & Parsing Baseline (Weeks 1-4)

**Goal**: Build a robust statement parser that achieves 95%+ accuracy on real-world PDFs.

**Key Deliverables**:

1. **Statement Parser Service** (MVP ready)
   - [ ] AWS Textract integration (primary PDF parser)
   - [ ] Unstructured.io fallback (local parsing)
   - [ ] PII masking layer (anonymize before storage)
   - [ ] Support 6+ bank formats (Chase, AmEx, Citi, Capital One, Discover, US Bank)
   - [ ] Unit tests: >90% code coverage for extraction logic

2. **Real-World Dataset Acquisition**
   - [ ] Collect 100+ anonymized statement samples (bank-diverse)
   - [ ] Create test dataset: 20% for validation, 80% for evaluation
   - [ ] Document ground truth (manually verify 50 statements)

3. **Evaluation Metrics** (Baseline)
   - [ ] Extraction accuracy: **95%+ for transaction date, amount, merchant**
   - [ ] Bonus accuracy: **90%+ for reward points extracted**
   - [ ] False positive rate: <2% (no hallucinated transactions)

**Success Criteria**:
- Parser successfully extracts transactions from 6+ bank formats with >95% accuracy
- No PII leakage in stored data
- Latency <5 seconds per statement (single PDF)

**Estimated Cost**: ~$500 (AWS Textract at scale, data collection labor)

---

### Phase 2: RAG Optimization & Evaluation (Weeks 5-8)

**Goal**: Build a reliable RAG pipeline with provable accuracy metrics (>90% faithfulness).

**Key Deliverables**:

1. **Reward Knowledge Service (RAG) with DeepEval**
   - [ ] Multi-bank benefit ingestion (500+ documents, 1000+ chunks)
   - [ ] LangChain orchestration with Claude 3.5 Sonnet / GPT-4o
   - [ ] DeepEval metrics: Faithfulness, Answer Relevancy, Context Precision (>85%+ targets)
   - [ ] Custom G-Eval metric: Financial Claim Accuracy (>95%, domain-specific)
   - [ ] Hallucination detection: <5% rate (automated + manual audits)
   - [ ] Fallback mechanism: Unclear answers → "Need clarification" prompt
   - [ ] Weekly eval runs on 100 historical queries via Confident AI platform

2. **Semantic Caching Layer**
   - [ ] Redis cache with 7-day TTL for stable queries
   - [ ] Monitor cache hit rate (target: >50%)
   - [ ] Cost reduction tracking: **Target 40% LLM cost reduction**

3. **Hybrid Retrieval Strategy**
   - [ ] Dense retrieval (semantic embeddings)
   - [ ] Sparse retrieval (BM25 keyword search)
   - [ ] Metadata filtering (card tier, bank, benefit category)
   - [ ] Re-ranking pipeline (score candidates, select top-3)

**Evaluation Dashboard**:
- [ ] Real-time metrics: Cache hit rate, hallucination count, response latency
- [ ] Weekly trend: Faithfulness score over time
- [ ] Alert threshold: Hallucination rate > 10/day → escalate

**Success Criteria**:
- **Financial Claim Accuracy** (DeepEval G-Eval): **>95%** (domain-specific, highest standard)
- **Faithfulness**: **>90%** (responses match source documents)
- **Answer Relevancy**: **>85%** (responses answer user intent)
- **Hallucination rate**: **<5%** (automated detection)
- Cache hit rate: **>50%** (reduces token cost by 40%+)
- Average response latency: <2 seconds (cached) / <4 seconds (uncached)

**Estimated Cost**: ~$2,000 (LLM API calls, Pinecone/Weaviate hosting, RAGAS evaluations)

---

### Phase 3: ROI & Cost Analysis Milestone (Weeks 9-10)

**Goal**: Prove system economics—ensure running cost is justified by user value delivered.

**Key Deliverables**:

1. **Token Cost Tracking & Optimization**
   - [ ] Log all LLM API calls (timestamp, tokens in/out, cost)
   - [ ] Identify expensive queries (>1000 tokens context)
   - [ ] Optimize prompts to reduce context size by 20-30%
   - [ ] Estimated monthly cost per user: <$0.50

2. **User Value Measurement**
   - [ ] Track recommendations accepted by users
   - [ ] Measure reward value unlocked (estimate from redemption patterns)
   - [ ] Example: If user saves $15 in rewards per month, value = $15; cost = $0.50; ROI = 30x

3. **Financial Dashboard**
   - [ ] Cost per recommendation (LLM token cost)
   - [ ] Value per recommendation (estimated reward savings)
   - [ ] Break-even analysis: When does recommendation value exceed system cost?
   - [ ] Payback period: How many days until user recoups system cost?

4. **Optimization Recommendations**
   - [ ] Batch processing for off-peak queries (reduce concurrency costs)
   - [ ] Fine-tune embedding model (smaller model = cheaper inference)
   - [ ] Adjust cache TTL (longer = better hit rate, but data staleness risk)

**Success Criteria**:
- Monthly system cost per user: **<$0.50**
- Estimated reward value per user: **>$10** (20x ROI minimum)
- Cost transparency: Dashboard shows token spend, API costs, breakdown

**Estimated Cost**: ~$1,000 (additional LLM API calls for analysis)

---

### Phase 4: Feedback Loop & Human-in-the-Loop (Weeks 11-12)

**Goal**: Establish a feedback mechanism to continuously improve recommendation quality.

**Key Deliverables**:

1. **Expert Verification System**
   - [ ] Identify low-confidence recommendations (DeepEval score <85% or Financial Accuracy <93%)
   - [ ] Route flagged recommendations to domain experts (financial advisors)
   - [ ] Experts review, approve, or correct recommendations
   - [ ] Store corrections as training data for prompt refinement
   - [ ] Log correction patterns in Confident AI for iteration improvement

2. **User Feedback Loop**
   - [ ] "Was this recommendation helpful?" thumbs up/down
   - [ ] "Did you follow this recommendation?" (yes/no)
   - [ ] Link feedback to recommendation → identify patterns in accuracy
   - [ ] Quarterly survey: "How much value did you save with the dashboard?"

3. **Continuous Improvement Pipeline**
   - [ ] Weekly: Identify questions with >3 expert corrections
   - [ ] Adjust retrieval strategy (change chunk size, metadata filters)
   - [ ] Update prompts based on expert feedback
   - [ ] A/B test: New retriever vs. old retriever on 10% of users
   - [ ] Deploy improved version only if A/B shows >5% improvement in satisfaction

4. **Monitoring & Alerts** (via Confident AI + Custom Dashboards)
   - [ ] Alert if Financial Accuracy score drops below 93%
   - [ ] Alert if expert correction rate jumps (e.g., 10% → 15% in a week)
   - [ ] Alert if cache hit rate drops (indicates stale data)
   - [ ] Alert if Faithfulness or Hallucination metrics decline
   - [ ] Real-time dashboard showing all DeepEval metric trends
   - [ ] Confident AI integration: Compare iterations, identify regression patterns

**Expert Workflow** (estimated 2-4 hours/week):
```
Flagged Recommendation
  ↓
Expert Review (Check against bank's official documentation)
  ↓
Decision: Approve / Correct / Flag as Ambiguous
  ↓
Store Feedback → Improve Prompt/Retriever
  ↓
Log Correction Type (Data issue? Prompt unclear? Retriever wrong?)
```

**Success Criteria**:
- Expert correction rate: **<5%** (90%+ recommendations are already good)
- User satisfaction score: **>4.2/5** (based on feedback surveys)
- Feedback loop latency: <1 week from expert correction to deployment of improved version

**Estimated Cost**: ~$2,000 (expert time: 4 hours/week × $50/hr × 12 weeks, LLM API calls)

---

### Post-Launch: Ongoing Optimization

**Ongoing Tasks** (Weeks 13+):

1. **Data Freshness**
   - [ ] Daily automated ingestion of bank benefit updates (Plaid API + web scraping)
   - [ ] Quarterly manual audit of critical benefit changes
   - [ ] Version control for metadata (track when rates change)

2. **Scalability**
   - [ ] Monitor database query latency (target: <100ms for Vector DB searches)
   - [ ] Upgrade to Pinecone's paid tier if hit rate >1000 requests/min
   - [ ] Shard data by bank for faster retrieval

3. **New Features** (Based on user feedback)
   - [ ] Expiry notifications for points (alert 30 days before expiration)
   - [ ] Cross-card comparison ("Best card for dining: Sapphire vs. Amex Gold")
   - [ ] Mobile app (iOS/Android)
   - [ ] Marketplace integrations (book flights, hotels directly in app)

4. **Compliance & Security**
   - [ ] Quarterly security audits (OWASP top 10)
   - [ ] Annual PCI-DSS compliance review
   - [ ] GDPR: Ensure "right to be forgotten" is implemented

---

## 12. MVP Scope (Hackathon Phase 1 Focus)

For the immediate hackathon demo, prioritize:

* PDF statement upload + parsing (Chase, AmEx)
* RAG-powered Q&A (basic version, no RAGAS yet)
* Semantic cache (to show cost optimization thinking)
* Dashboard showing parsed transactions + reward balance
* Simple redemption recommendations (rule-based)

**Out of scope for hackathon** (Roadmap Phase 2+):
- Full evaluation framework (RAGAS/TruLens)
- Multi-bank coverage (100+)
- Human-in-the-loop verification
- Advanced ROI dashboard

---

## 13. Summary

This updated architecture now includes:

✅ **Production-grade security**: PII handling, data masking, encryption  
✅ **Evaluation framework**: **DeepEval** with custom G-Eval for financial domain  
✅ **Cost optimization**: Semantic caching for 40%+ token savings  
✅ **Real-world data strategy**: Multi-bank support, metadata enrichment  
✅ **Specific tech stack**: Claude 3.5 Sonnet, LangChain, AWS Textract, Pinecone  
✅ **Phased roadmap**: Clear milestones from parsing → evaluation → ROI → feedback  
✅ **Cloud observability**: Confident AI platform for iteration tracking & monitoring  

The modular design allows each phase to be completed independently, with measurable success criteria and ROI tracking. This positions the project as both a **hackathon showcase** and a **path to production**.
