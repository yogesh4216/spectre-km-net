from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import sqlite3
import pandas as pd
from datetime import datetime
import os
import shutil
import tempfile
import json
from processor import process_mri, generate_report_content, generate_pdf_report
from fastapi.responses import HTMLResponse, FileResponse

app = FastAPI()

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "neurovis_ehr.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS patient_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date_saved TEXT,
                  patient_name TEXT,
                  mrn TEXT,
                  age INTEGER,
                  diagnosis TEXT,
                  location TEXT,
                  total_vol_cc REAL,
                  necrosis_cc REAL,
                  edema_cc REAL,
                  active_tumor_cc REAL,
                  report_path TEXT)''')
    
    # Create master data directory
    if not os.path.exists("patient_data"):
        os.makedirs("patient_data")
    
    past_date = "2025-11-15 10:00:00"
    c.execute("SELECT COUNT(*) FROM patient_history WHERE date_saved = ?", (past_date,))
    if c.fetchone()[0] == 0:
        c.execute('''INSERT INTO patient_history 
                     (date_saved, patient_name, mrn, age, diagnosis, location, total_vol_cc, necrosis_cc, edema_cc, active_tumor_cc)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                  (past_date, "John Doe", "GLI-02547-101", 45, "Glioblastoma Multiforme (HGG)", "Right Parietal Lobe", 28.45, 0.0, 24.33, 4.12))
    
    conn.commit()
    conn.close()

def get_patient_dir(mrn):
    path = os.path.join("patient_data", mrn.replace("-", "_"))
    if not os.path.exists(path):
        os.makedirs(path)
    return path

init_db()

@app.get("/patients")
def get_patients():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM patient_history ORDER BY date_saved DESC", conn)
    conn.close()
    return df.to_dict(orient="records")

@app.get("/patients/{mrn}")
def get_patient_history(mrn: str):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM patient_history WHERE mrn = ? ORDER BY date_saved DESC", conn, params=(mrn,))
    conn.close()
    return df.to_dict(orient="records")

@app.post("/save_record")
def save_record(
    patient_name: str = Form(...),
    mrn: str = Form(...),
    age: int = Form(...),
    diagnosis: str = Form(...),
    location: str = Form(...),
    total_vol_cc: float = Form(...),
    necrosis_cc: float = Form(...),
    edema_cc: float = Form(...),
    active_tumor_cc: float = Form(...)
):
    vols = {
        'total': total_vol_cc,
        'necrosis': necrosis_cc,
        'edema': edema_cc,
        'enhancing': active_tumor_cc
    }
    
    # Get patient folder
    pat_dir = get_patient_dir(mrn)
    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M")
    pdf_filename = f"Report_{timestamp_slug}.pdf"
    pdf_path = os.path.join(pat_dir, pdf_filename)
    
    # Generate PDF
    generate_pdf_report(patient_name, mrn, age, diagnosis, location, vols, pdf_path)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''INSERT INTO patient_history 
                 (date_saved, patient_name, mrn, age, diagnosis, location, total_vol_cc, necrosis_cc, edema_cc, active_tumor_cc, report_path)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
              (timestamp, patient_name, mrn, age, diagnosis, location, total_vol_cc, necrosis_cc, edema_cc, active_tumor_cc, pdf_path))
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Record and PDF for {patient_name} saved in portal folders."}

@app.get("/download_pdf/{record_id}")
def download_pdf(record_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT report_path FROM patient_history WHERE id = ?", (record_id,))
    row = c.fetchone()
    conn.close()
    
    if row and row[0] and os.path.exists(row[0]):
        return FileResponse(path=row[0], filename=os.path.basename(row[0]), media_type='application/pdf')
    raise HTTPException(status_code=404, detail="PDF report not found")

@app.post("/generate_report")
def handle_generate_report(
    patient_name: str = Form(...),
    mrn: str = Form(...),
    age: int = Form(...),
    diagnosis: str = Form(...),
    location: str = Form(...),
    total_vol_cc: float = Form(...),
    necrosis_cc: float = Form(...),
    edema_cc: float = Form(...),
    active_tumor_cc: float = Form(...)
):
    vols = {
        'total': total_vol_cc,
        'necrosis': necrosis_cc,
        'edema': edema_cc,
        'enhancing': active_tumor_cc
    }
    report_html = generate_report_content(patient_name, mrn, age, diagnosis, location, vols)
    return HTMLResponse(content=report_html)

@app.post("/process_mri")
async def handle_process_mri(
    files: List[UploadFile] = File(...),
    pat_id: str = Form("UNKNOWN") # MRN from frontend
):
    file_map = {}
    temp_files = []
    
    try:
        # Get patient directory early for storage
        pat_dir = get_patient_dir(pat_id)
        scan_dir = os.path.join(pat_dir, "scans", datetime.now().strftime("%Y%m%d_%H%M%S"))
        if not os.path.exists(scan_dir):
            os.makedirs(scan_dir)

        for f in files:
            name = f.filename.lower()
            suffix = ".nii.gz" if name.endswith(".gz") else ".nii"
            
            # Save to patient folder directly
            perm_path = os.path.join(scan_dir, f.filename)
            with open(perm_path, "wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            
            temp_files.append(perm_path)
            
            if 'seg' in name: file_map['seg'] = perm_path
            elif 't1n' in name: file_map['t1'] = perm_path
            elif 't1c' in name: file_map['t1ce'] = perm_path
            elif 't2f' in name: file_map['flair'] = perm_path
            elif 't2w' in name: file_map['t2'] = perm_path
        
        if 'seg' in file_map and ('t1' in file_map or 't1ce' in file_map):
            anat_path = file_map.get('t1ce', file_map.get('t1'))
            seg_path = file_map['seg']
            
            result = process_mri(anat_path, seg_path)
            return result
        else:
            raise HTTPException(status_code=400, detail="Missing required MRI sequences (Anatomy and SEG).")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
