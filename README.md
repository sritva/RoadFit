# RoadFit-X: Risk-Aware Vehicle-Conditioned Routing on Incomplete Road Graphs

> RoadFit-X mathematically models the physical constraints of a vehicle against the probabilistic layout of a road network, generating Pareto-optimal routes that balance Travel Time against Physical Traversal Risk.

Standard navigation engines (like Google Maps) optimize purely for travel time or distance. They assume that if an edge exists in the road graph, it is perfectly traversable. When routing heavy delivery vehicles, emergency responders, or logistics fleets through dense, undocumented residential grids (like those found in Bengaluru, India), this assumption fails catastrophically.

RoadFit-X transitions routing from a shortest-path heuristic to a **Multi-Label $\epsilon$-Dominance Optimization Problem**. It proves that when explicit graph data is missing (100% Missing Data Exposure), unconstrained routing incurs catastrophic **Tail-Risk**, and strict risk-policies can trace the true Pareto frontier of Safety vs. Efficiency.

---

## 1. Core Architecture

RoadFit-X is composed of three interconnected layers:

### The Data Layer (Heterogeneous Map Enrichment)
OpenStreetMap (OSM) heavily under-tags critical physical constraints (e.g., `width`, `maxweight`). RoadFit-X employs statistical map enrichment—injecting expected physical bounds based on topological features (`highway` tags, connectivity) while intentionally preserving a missing data rate. This accurately models the real-world uncertainty inherent in public geographic datasets.

### The Mathematical Engine (Multi-Label Risk Optimization)
RoadFit-X discards standard $A^*$ for a multi-label graph traversal. Each edge evaluation accumulates a three-dimensional vector: $(T, U, C_{\min})$:
1. **$T$ (Travel Time)**: The physical duration integral of the path.
2. **$U$ (Uncertainty & Risk Penalty)**: A probabilistic penalty derived from missing data and adverse traffic/weather conditions.
3. **$C_{\min}$ (Clearance Margin)**: The absolute spatial bottleneck constraining the vehicle.

Using **$\epsilon$-Dominance Bucketing**, the engine prunes sub-optimal paths to compute the true Pareto frontier, completely avoiding the exponential blow-up typically associated with multi-objective shortest path (MOSP) problems.

### The Interactive Application (Live Validation Dashboard)
A premium React/MapLibre frontend natively visualizes these trade-offs. The interface allows researchers to select vehicle digital twins, toggle missing data policies (Strict, Conservative, Exploratory), and instantly visualize how RoadFit-X geometrically detours to avoid the bottlenecks that traditional unconstrained routers (Baseline $B_0$) crash into.

---

## 2. Setting Up RoadFit-X on a New System

### Prerequisites
- Python 3.10+
- Node.js 18+
- Git

### Backend Setup (FastAPI & Engine)
1. Clone the repository:
   ```bash
   git clone <your-repo-url>
   cd roadfit
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\Activate.ps1
   # Linux/Mac:
   source venv/bin/activate
   ```
3. Install the mathematical and server dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. **Data Generation**: Run the statistical enrichment script to simulate missing data topologies:
   ```bash
   python src/data/enrich_graph.py
   ```
5. Start the API Server:
   ```bash
   python -m src.api.server
   ```
   *(The server will start on `http://127.0.0.1:8000`)*

### Frontend Setup (React Dashboard)
1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install Node dependencies:
   ```bash
   npm install
   ```
3. Setup environment variables:
   ```bash
   # Windows
   copy .env.example .env
   # Linux/Mac
   cp .env.example .env
   ```
4. Start the Vite development server:
   ```bash
   npm run dev
   ```
5. Open your browser and navigate to `http://localhost:5173`.

---

## 3. Academic Benchmarking
To run the automated 100 OD-Pair statistical analysis that proves the Pareto Frontier:
```bash
python -m src.evaluation.ablations --graph data/koramangala_enriched_v2.graphml --num-pairs 100 --output results_100_od.csv
```
Once generated, plot the CDF and Pareto curves using:
```bash
python src/evaluation/plot_results.py --csv results_100_od.csv
```

## 4. Documentation
For a complete, deep-dive into the mathematical proofs, architectural flaws fixed, and future research goals, please see [PROJECT_DEEP_DIVE.md](docs/PROJECT_DEEP_DIVE.md).
