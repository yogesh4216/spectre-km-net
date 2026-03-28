# SPECTRAL-KM-NET | Clinical Portal

**SPECTRAL-KM-NET** is a comprehensive, full-stack application explicitly built for clinical analysis of MRI sequences, automated segmentation, and secure reporting. It includes a resilient FastAPI Python backend driving the automated metrics, paired securely with a pristine, vanilla frontend.

---

## 🚀 Features

- **Automated Volumetric Generation**: Processes T1, T1c, T2, FLAIR, and SEG (NIfTI) sequences on the backend.
- **Dynamic 3D Plotting**: Utilizes frontend WebGL to visualize patient MRI outcomes using Plot.ly.
- **Longitudinal EHR Data Base**: Tracks patient outcomes and progressions over time securely via an embedded SQLite Engine. 
- **PDF Report Generation**: Quickly generate full, aesthetic clinician-ready PDF summaries immediately upon assessment completion.
- **Premium Glassmorphism Aesthetic**: Implements cutting-edge dark-mode transparency and interactive responsive components without any frontend-framework overhead.

---

## 🏗️ Architecture

- **Backend**: Python 3.12+, FastAPI, Uvicorn, Pandas, SQLite3, NiBabel (for volumetric MRI parsing).
- **Frontend**: Vanilla HTML5, CSS3, JavaScript (ES Modules). Served locally without complicated build pipeline requirements.
- **Icons & Graphing**: Plotly.js, Lucide Icons.

---

## ⚙️ How to Run Locally

### 1. Setup Backend Server
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
# API runs on http://0.0.0.0:8000
```

### 2. Setup Frontend Server
Because the frontend has zero framework dependencies locally, it can be seamlessly attached to any local development server.

```bash
cd frontend
python3 -m http.server 5173
# Portal is now accessible on http://localhost:5173
```

---

## 🗂️ Project Structure

- `backend/`
  - `main.py`: The FastAPI core routing the MRI volumetric APIs and Database.
  - `processor.py`: Internal business logic that processes NIfTI data, converts to visual meshes, and drafts PDFs.
  - `patient_data/`: Automatically generated directory that stores patient history and PDF evaluations securely.
  
- `frontend/`
  - `index.html`: Main interactive clinical dashboard view.
  - `main.js`: Core ES module for REST API communication.
  - `style.css`: Comprehensive CSS stylesheets utilizing high-end UI design conventions.
