# RoadFit

RoadFit is a vehicle-aware hyperlocal routing prototype built around OSM road graphs, custom vehicle constraints, and a FastAPI backend plus a Vite React frontend.

## Quick start

### 1) Python backend

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000
```

### 2) Frontend

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

The frontend reads the backend URL from `VITE_API_BASE_URL`.

## Notes

- The project relies on a local OSM GraphML dataset in the `data/` folder.
- The API is intentionally prototype-grade and uses the shipped graph data for route comparisons.
- Some modules (benchmarking and traffic simulation) are mock/demo oriented unless real APIs are configured.

## Existing data workflow

```powershell
./run_test.ps1
```
