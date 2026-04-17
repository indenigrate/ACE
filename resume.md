# **Devansh Soni | Systems Architect & Technical Leader**

**Student at IIT Kharagpur | Technology Coordinator (TSG) | Executive Head (DevSoc)**

I am a product-focused engineer who operates at the intersection of **distributed systems, agentic AI, and institutional infrastructure**. My work is defined by a refusal to accept "black box" abstractions; I build custom architectures—from low-level HTTP servers to state-aware AI agents—to ensure performance, type safety, and scalability.

---

### **0. Education**
*   **Indian Institute of Technology Kharagpur** | B.Tech in Chemical Engineering | **CGPA: 8.62** | 2023 – 2028
*   **Billabong High International School** | H.S.C: **95.6%** (2023) | S.S.C: **97.2%** (2021)

---

### **1. Magnum Opus: Agentic AI Systems**

#### **ACE (Agentic Cold Emailer)**
*Core Tech: Python, LangGraph, Vertex AI, Gmail API, Google Sheets, Serper API*
*   Engineered an **autonomous agentic workflow** to streamline internship outreach, reducing the time required per personalized email from **20 minutes to just 20 seconds** by parallelizing company research and draft generation.
*   Implemented a **Human-in-the-Loop** architecture enabling real-time user review of AI drafts before dispatching, while automatically synchronizing status updates with Google Sheets.
*   Built **A/B subject line testing** with 3 LLM-generated variants per email and **automated threaded follow-ups** via Gmail API, with robust error handling for missing threads.
*   Developed a **campaign analytics engine** tracking conversion funnels, skip-reason breakdowns, and per-lead status across the entire pipeline.
*   Architected a **multi-stakeholder enrichment pipeline** using Google Search API + Gemini to discover multiple key contacts (CEO, CTO, VPs) per company, minimizing API costs with a two-step search-then-parse strategy.


#### **Conversational Survey Agent**
*Core Tech: LangGraph, Python, Google Gemini, Redis, Firestore*
*   **Finite State Machine (FSM) Architecture:** Utilized `LangGraph` to enforce strict state transitions, ensuring the bot adheres to a rigorous JSON schema for data collection.
*   **"The Weave" Conversation Strategy:** Engineered a prompt strategy that forces the model to **Validate** emotion, **Bridge** topics, and **Ask** questions covertly in every turn.
*   **Custom Middleware Layer:** 
    *   **`FrustrationGuardMiddleware`:** Tracks user sentiment to prevent infinite loops by overriding the LLM if a user becomes stuck.
    *   **`bootstrap_session_middleware`:** Ensures session state is initialized correctly before the LLM generates any tokens.
*   **Async Persistence:** Developed a custom `AsyncFirestoreSaver` for non-blocking checkpointing, enabling high concurrency.

---

### **2. Distributed Systems & Hard Engineering**

#### **WikiHunt-Bot (The Pathfinding Service)**
*   **The Challenge:** Calculating the shortest path between Wikipedia articles via concurrent graph traversal.
*   **The Solution:** Decoupled architecture into **Go** (for high-concurrency traversal via Goroutines) and **Python** (for semantic intelligence via **Sentence-BERT**).
*   **The Impact:** Slashed average pathfinding latency by over **90%** (from 3+ minutes to <20 seconds) and reduced operational costs by 50% through intelligent batching.

#### **HTTP/1.1 Server (From Scratch)**
*Core Tech: Go, TCP/IP, Concurrency*
*   Built a high-performance server by interacting directly with **raw TCP sockets**, manually parsing byte streams to eliminate standard library overhead.
*   Implemented **Gzip compression**, **TCP Keep-Alive**, and **Goroutine-based concurrency** for low-latency client handling.

---

### **3. Institutional Infrastructure (Scale: 10,000+ Users)**

#### **Technology Coordinator @ TSG, IIT Kharagpur**
*   **Induction Portal:** Managed the full-stack lifecycle for a platform serving **2,000+ students**, maintaining **99.9% uptime** during peak registration.
*   **Digital Transformation:** Directed the development of an automated library check-in system that **reduced manual processing time by 90%**.
*   **Team Leadership:** Manage a team of **5+ Web Secretaries**, coordinating technical proposals for institute-wide technology goals.

#### **Executive Head @ Developers' Society (DevSoc)**
*   **Agentic AI Workshop:** Orchestrated a flagship workshop training **350+ students** in building autonomous AI systems.
*   **App Restoration:** Led the revival of the **'ApnaInsti'** campus application, resolving legacy bugs and restoring full functionality for the student body.

---

### **4. Foundational Projects (Commented Archives)**
*   **Attendance Monitor (Go, PostgreSQL):** Architected a production-ready system with a secure JWT-based RESTful API and a normalized schema designed to scale to thousands of records.
*   **Job Listing API (Go, Docker):** Orchestrated a microservices application using Docker Compose, slashing developer setup time by **95%**.

---

### **5. Technical Arsenal**

| Domain | Primary Tools & Methodology |
| --- | --- |
| **Agentic AI** | **LangGraph, LangChain, Vertex AI.** State-aware agents with custom middleware. |
| **Backend** | **Go (Gin, pgx), Python (FastAPI).** High-throughput microservices and AI integration. |
| **Database** | **PostgreSQL, Redis, Firestore, MongoDB.** Normalized schemas and NoSQL session state. |
| **DevOps** | **Docker, AWS, GCP, Nginx, Linux (Arch).** Containerization and reverse proxy management. |
| **Languages** | **Go, Python, C/C++, SQL, Bash, JavaScript.** |

---

### **6. Extra-Curricular Activities**
*   **Leadership:** Vice-Captain for the Interhall Basketball Championship.
*   **Arts:** Actor and Co-writer for Nukkad (Street Play) competitions.
*   **Photography:** Personal project on Pexels with over **40,000 views**.

---

### **Summary**
I am a **Product-Grade Engineer**. I have shipped code used by thousands of users, reduced operational costs through algorithmic optimization, and led technical teams to deliver critical campus infrastructure. I am ready to drop into a high-velocity engineering team and own the entire lifecycle of a product—from the Linux kernel up to the React frontend.
