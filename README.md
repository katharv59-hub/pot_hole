# ROADSentinel v0.4

> **Road Hazard Detection & Spatial Intelligence Platform**  
> Real-time ESP32 edge telemetry ingestion, rule-based & ML classification, PostGIS spatial indexing, and Mapbox GL JS visualization.

---

## 1. System Architecture

```text
ESP32 Hardware (IMU + GPS)
        ↓ (HTTP POST /events)
FastAPI Ingestion Engine
        ↓ (Rule-based / ML verification)
PostgreSQL 16 + PostGIS 3.6 Datastore (GiST spatial indexing)
   ├── WebSocket Real-time Broadcast
   └── REST API (/events, /analytics, /routes/safety, /media)
        ↓
Mapbox GL JS & React 18 Frontend
```

---

## 2. Prerequisites

- **Python:** 3.11+
- **Node.js:** 18+ (npm 9+)
- **Database:** PostgreSQL 16+ with PostGIS 3.6+ extension
- **Mapbox Token:** Free public token from [mapbox.com](https://www.mapbox.com/)

---

## 3. Database Setup (PostgreSQL + PostGIS)

1. Ensure the PostgreSQL service is running on `localhost:5432`.
2. Connect to PostgreSQL and create the database with PostGIS:

```sql
CREATE DATABASE roadsentinel;
\c roadsentinel
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Version();
```

---

## 4. Backend Configuration & Startup

1. Navigate to `backend/` and install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Configure environment variables in `backend/.env` (refer to `backend/.env.example`):
   ```env
   SECRET_KEY=your-secure-random-64-character-secret-key-here
   DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:5432/roadsentinel
   MAPBOX_ACCESS_TOKEN=pk.your_mapbox_public_token
   GOOGLE_MAPS_API_KEY=your_optional_google_directions_api_key
   STORAGE_PROVIDER=local
   ```

3. Run Alembic migrations:
   ```bash
   alembic upgrade head
   ```

4. Bootstrap initial admin account (optional seed):
   ```bash
   python seed.py
   ```

5. Start the backend server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   - API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
   - WebSocket Transport: `ws://localhost:8000/ws`

---

## 5. Frontend Configuration & Startup

1. Navigate to `frontend/` and install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Configure environment variables in `frontend/.env` (refer to `frontend/.env.example`):
   ```env
   VITE_API_BASE_URL=http://localhost:8000/api/v1
   VITE_WS_URL=ws://localhost:8000/ws
   VITE_MAPBOX_ACCESS_TOKEN=pk.your_mapbox_public_token
   ```

3. Start development server:
   ```bash
   npm run dev
   ```

4. Build production bundle:
   ```bash
   npm run build
   ```

---

## 6. Running Automated Tests

Run the complete backend test suite (67 tests across all 10 architectural phases):

```bash
cd backend
python -m pytest
```

---

## 7. Role-Based Access Control (RBAC) Matrix

| Resource / Action | Driver | Admin | Authority | Device Token |
|---|:---:|:---:|:---:|:---:|
| **Hazard Map / Catalog** | ✅ | ✅ | ✅ | ❌ |
| **Manual Reports** | ✅ (own) | ✅ (all) | ✅ (all) | ❌ |
| **Event Ingestion** | ❌ | ❌ | ❌ | ✅ (assigned vehicle only) |
| **Status Moderation** | ❌ | ✅ | ✅ | ❌ |
| **Device Provisioning & Revocation** | ❌ | ✅ | ❌ | ❌ |
| **Spatial Analytics & CSV Export** | ❌ | ✅ | ✅ | ❌ |
| **Media (Raw Tier)** | ✅ (own) | ✅ | ✅ | ❌ |
| **Media (Processed Tier)** | ✅ | ✅ | ✅ | ❌ |

---

## 8. License

ROADSentinel Engine is licensed under the Apache 2.0 License.
