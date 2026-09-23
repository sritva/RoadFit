# RoadFit-X: Project Deep Dive

## 1. Project Context & Motivation
RoadFit-X was conceptualized to solve a glaring vulnerability in modern geospatial computing: standard shortest-path algorithms assume complete and truthful map data. If an edge exists in a graph, it is considered perfectly traversable. However, in dense, hyperlocal urban environments (like Bengaluru or older European city centers), OpenStreetMap lacks physical constraints (width, height, weight limitations). This results in delivery vans and emergency vehicles being routed into physically impassable alleys, resulting in catastrophic route failures.

The goal of RoadFit-X is to transition routing from a *geometric shortest-path problem* to a *multi-objective, risk-aware probabilistic decision problem*. 

## 2. Flaws Addressed (The A* Refactoring)
In Phase 1 and 2, the system utilized a naive, unconstrained A* traversal that attempted to penalize unknown data retroactively using ad-hoc coefficients. 

### The Flaws:
1. **Mathematical Invalidation (Bellman's Principle):** Path costs were not monotonically non-decreasing, and uncertainty was injected heuristically. This invalidated A* optimality and prevented any Pareto-front evaluation.
2. **Missing Data Masking:** The Koramangala subgraph used for testing had a Missing Data Exposure Fraction (MDEF) of 100%. Because no width tags existed, any policy evaluating risk would completely collapse or reject the entire graph.
3. **Data Leakage in Evaluation:** The metrics engine was incorrectly grading the route's success based on imputed (simulated) data rather than verified ground truth, rendering any academic claims void.

### The Fixes:
1. **Multi-Label $\epsilon$-Dominance Search:** The core engine (`risk_aware_router.py`) was entirely rewritten. Instead of tracking a single cost $g$, it tracks a 3D state vector $(T, U, C_{\min})$ representing Travel Time, Uncertainty, and Clearance. A quantization threshold ($\epsilon = 0.2\text{m}$) discretizes the continuous bottleneck space, allowing us to prune strictly dominated paths and extract a true Pareto frontier.
2. **Statistical Heterogeneity Injection:** A new module (`enrich_graph.py`) was created to statistically generate physical road constraints based on OSM topology, while intentionally randomly dropping 30% of them. This synthetically creates the heterogeneity required to benchmark risk without a trillion-dollar LiDAR budget.
3. **Strict Validation Protocols:** `metrics_engine.py` was rewritten to produce canonical academic metrics (ISER, CNME, TRR, ETTP).
4. **Interactive Dashboard:** The React frontend was overhauled into an academic validation dashboard, visualizing the geometric detours dynamically comparing a $B_0$ (Unconstrained Baseline) against the Multi-Label RoadFit-X solution.

## 3. Academic Metrics 
To submit this to a top-tier conference (ACM SIGSPATIAL, IEEE ITSC), we measure the following:
- **TRR (Tail-Risk Ratio):** $\frac{\text{Failure Risk}}{\text{Distance}}$. A lower TRR means the vehicle is significantly less likely to get physically stuck.
- **ETTP (Excess Travel Time Penalty):** The percentage of time added by taking the safer detour. $\frac{T_{\text{model}} - T_{B_0}}{T_{B_0}}$.
- **MDEF (Missing Data Exposure Fraction):** The percentage of the chosen route that lacks explicit ground-truth width measurements.
- **ISER (Infeasible Segment Exposure Rate):** The hard failure rate. RoadFit-X should maintain an ISER of $0.0\%$.

## 4. Next Fixes and Suggested Work
To push this project to an A* status, the following items are suggested:
1. **GNN Integration (v3.1):** A PyTorch Geometric model is partially scaffolded but not integrated. Training a Graph Attention Network (GAT) on edge features (centrality, length, topology) to predict the $30\%$ missing width distributions would replace the naive `enrich_graph.py` heuristic with a fully differentiable graph-learning pipeline.
2. **Dynamic Bounding Box Control:** Currently, users dropping pins far outside the local pre-loaded Koramangala graph will trigger an active `osmnx` download. A hard $50\text{km}$ limit was added to prevent server hangs, but this needs to be decoupled into a celery worker or background task with proper frontend loading states.
3. **Real-time Map-Matching:** Integrating GPS trajectories to organically lower the Uncertainty ($U$) penalty over edges that fleets frequently traverse without issues.

## 5. Setting up on a Different System
Follow these explicit steps to transfer this environment to a new lab machine or cluster:

1. **Clone the Repo:** 
   `git clone <repository_url>`
2. **Build Python Backend:**
   `python -m venv venv`
   `source venv/bin/activate` (or `.\venv\Scripts\Activate.ps1` on Windows)
   `pip install -r requirements.txt`
3. **Synthesize Data (Crucial):**
   *Do not skip this, or your MDEF will be 100% and routes will fail.*
   `python src/data/enrich_graph.py`
4. **Start the API:**
   `python -m src.api.server`
5. **Build the Frontend:**
   `cd frontend`
   `npm install`
   `cp .env.example .env` (ensure VITE_API_BASE_URL points to the python server)
   `npm run dev`
6. **Access:** Open a modern web browser to `http://localhost:5173`.
