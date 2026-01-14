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
Convert raw statements into structured transaction and reward data.

**Input**:

* PDF statements
* Email statements (future)

**Processing Steps**:

1. PDF ingestion
2. Text extraction (OCR if needed)
3. Pattern-based + LLM-assisted parsing
4. Normalization to JSON schema

**Output**:

* Transactions
* Monthly reward points
* Card metadata

---

### 4.2 Reward Knowledge Service (RAG)

**Purpose**:
Provide accurate, contextual answers about credit card benefits, rules, and redemption options.

#### RAG Pipeline

**Ingestion Sources**:

* Bank websites (HTML/PDF)
* Card benefit documents
* Third-party comparison portals

**Embedding & Storage**:

* Chunk size: 512–1024 tokens
* Embedding models:

  * `text-embedding-3-large`
  * `bge-large`
* Stored in Vector Database with metadata

**Retrieval & Generation**:

1. User query embedding
2. Vector similarity search
3. Context assembly
4. LLM response generation

---

### 4.3 Recommendation Engine

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

## 5. Data Storage Layer

### 5.1 SQL Database

Stores structured, transactional data.

**Entities**:

* Users
* Credit Cards
* Transactions
* Reward Balances

**Examples**:

* PostgreSQL
* MySQL

---

### 5.2 Vector Database

Stores embedded credit card benefit documents.

**Examples**:

* Pinecone
* Weaviate
* Qdrant

**Metadata**:

* Bank name
* Card name
* Benefit category (Travel, Dining, Cashback)

---

### 5.3 Object Storage

Stores raw documents.

**Examples**:

* AWS S3
* GCP Cloud Storage
* Azure Blob Storage

**Contents**:

* PDF statements
* Scraped HTML/PDF benefit docs

---

## 6. Security Considerations

* Secure file upload handling
* Encryption at rest & in transit
* Masking sensitive PII
* Token-based API access
* No long-term storage of raw credentials

---

## 7. MVP Scope (Hackathon)

The MVP will demonstrate:

* PDF statement upload
* Parsing reward points for at least one card
* RAG-powered benefit Q&A
* Dashboard UI with summary metrics
* Simple redemption recommendation

---

## 8. Future Enhancements

* Auto-scraping bank benefit updates
* Expiry notifications & alerts
* Cross-card comparison engine
* Mobile application
* Marketplace integrations (flights, hotels)
* Advanced personalization using ML

---

## 9. Summary

This architecture balances **speed**, **clarity**, and **scalability**, making it ideal for a hackathon while laying the groundwork for a production-ready fintech AI platform. The modular service design allows independent evolution of parsing, RAG, and recommendation logic.
