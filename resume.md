# **Devansh Soni | Systems Architect & Technical Leader**

**Student at IIT Kharagpur | Technology Coordinator (TSG) | Executive Head (DevSoc)**

I am a product-focused engineer who operates at the intersection of **distributed systems, agentic AI, and institutional infrastructure**. My work is defined by a refusal to accept "black box" abstractions; I build custom architectures—from low-level HTTP servers to state-aware AI agents—to ensure performance, type safety, and scalability.

---

### **1. Magnum Opus: The "Agentic" Conversational Engine**

*Core Tech: LangGraph, Python, Google Gemini, Redis, Firestore*

I architected a production-grade **Conversational Form Agent** designed to replace static HTML forms with a fluid, human-like interview process. This was not a simple wrapper around an LLM; it was a strictly typed, event-driven state machine.

* **Finite State Machine (FSM) Architecture:** I utilized `LangGraph` to enforce strict state transitions (`ONGOING`  `CLARIFYING`  `FINISHED`). This ensured the bot never hallucinated its progress and adhered to a rigorous JSON schema for data collection.
* **"The Weave" Conversation Strategy:** I engineered a specific prompt strategy called "The Weave," which forced the model to perform three distinct actions in every turn: **Validate** the user's emotion, **Bridge** the topic, and **Ask** the next question covertly.
* **Custom Middleware Layer:** To ensure reliability, I wrote custom middleware directly into the graph:
* **`FrustrationGuardMiddleware`:** I implemented a safety valve that tracks `consecutive_flags`. If a user gets stuck or frustrated (fails to answer 3 times), the system automatically overrides the LLM to skip the question, preventing infinite loops.
* **`bootstrap_session_middleware`:** I created logic to intercept the very first action, forcing the `load_survey` tool to execute before the LLM ever generates a token, ensuring the session state is always initialized correctly.


* **Async Persistence:** I wrote a custom `AsyncFirestoreSaver` to handle checkpointing. This allowed the system to be non-blocking and capable of handling high concurrency by writing to Google Firestore asynchronously, rather than relying on synchronous writes that would bottleneck the chat flow.

---

### **2. Distributed Systems & Hard Engineering**

My approach to engineering is "systems-first." I prioritize memory safety and concurrency.

* **WikiHunt-Bot (The Pathfinding Service):**
* **The Challenge:** Calculating the shortest path between Wikipedia articles requires efficient graph traversal and semantic understanding of content.
* **The Solution:** I decoupled the architecture into microservices. I built the traversal engine in **Go** to leverage goroutines for concurrent processing, while the semantic intelligence was handled by a **Python** service using **Sentence-BERT**.
* **The Impact:** By implementing intelligent batching and semantic heuristics, I reduced pathfinding latency for the **WikiHunt-Bot** from **3+ minutes to under 20 seconds** (a 90% reduction) and cut API costs by 50%.

---

### **3. Institutional Infrastructure (Scale: 10,000+ Users)**

As the **Technology Coordinator** for the Technology Students' Gymkhana, I don't just write code; I manage the digital backbone of the IIT Kharagpur campus.

* **ApnaInsti (Campus Super-App):**
* I lead the development and maintenance of **ApnaInsti**, the primary digital gateway for 10,000+ students. I oversee the integration of institute-wide services and ensure the app remains the central hub for campus life.
* **TSG Induction Portal:**
* I managed the registration of **2,000+ students** concurrently for the induction process. By optimizing the deployment via Docker and Nginx, I ensured system stability and high availability during peak registration traffic.
* **Security:** I implemented security protocols and authentication systems to ensure data sovereignty between students and administration.

---

### **4. Strategic Leadership & Vision**

My role extends beyond the terminal; I define technical strategy and lead teams to execute it.

* **Executive Head @ Developers' Society (DevSoc):**
* I revitalized the society by restructuring the recruitment process and internal workflows.
* **Visionary Events:** I organized technical sessions featuring industry leaders like **Gaurav Sen** (Founder, InterviewReady) to bridge the gap between student developers and top-tier engineering firms.
* **Team Management:**
* I lead a team of **5+ Web Secretaries**, overseeing code reviews, architectural decisions, and the deployment lifecycle for institute-wide technology goals.





---

### **5. My Technical Arsenal**

I curate my stack for performance, control, and immutability.

| Domain | Primary Tools & Methodology |
| --- | --- |
| **Agentic AI** | **LangGraph, LangChain.** I build state-aware agents with custom middleware and persistence layers. |
| **Backend** | **Go (Gin), Python (FastAPI).** I use Go for high-throughput microservices and Python for AI/ML integration. |
| **Database** | **PostgreSQL, Firestore, Redis.** I design normalized schemas (3NF) for integrity and use NoSQL for session state. |
| **DevOps** | **Docker, Nginx, AWS.** I containerize environments to eliminate "works on my machine" issues and manage reverse proxies for production load balancing. |
| **OS Environment** | **Arch Linux (Hyprland).** I am a power user who optimizes my workflow via the terminal and shell scripting. |

---

### **Summary**

I am a **Product-Grade Engineer**. I have shipped code used by thousands of users, reduced operational costs through algorithmic optimization, and led technical teams to deliver critical campus infrastructure along with building end to end ai agents completely. I am ready to drop into a high-velocity engineering team and own the entire lifecycle of a product—from the Linux kernel up to the React frontend.