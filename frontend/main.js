// --- CONFIG ---
const API_BASE = "http://localhost:8000";

// --- STATE ---
let uploadedFiles = [];
let analysisResult = null;
let currentView = "new-scan"; // or "database"
let dbViewMode = "directory"; // or "history"

// --- DOM ELEMENTS ---
const tabs = document.querySelectorAll('.nav-links li');
const tabSections = document.querySelectorAll('.tab-content');
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file_input');
const fileList = document.getElementById('file-list');
const btnProcess = document.getElementById('btn-process');
const loadingOverlay = document.getElementById('loading-overlay');
const analysisPlaceholder = document.getElementById('analysis-placeholder');
const analysisResults = document.getElementById('analysis-results');
const btnNewPatient = document.getElementById('btn-new-patient');

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initNavigation();
    initFileUpload();
    initDatabase();
    
    btnProcess.addEventListener('click', handleProcess);
    btnNewPatient.addEventListener('click', resetApp);
    document.getElementById('btn-save-db').addEventListener('click', handleSaveToDB);
    document.getElementById('btn-download-report').addEventListener('click', handleDownloadReport);
    document.getElementById('db-search').addEventListener('input', (e) => filterDatabase(e.target.value));
    
    document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            switchDBView(e.target.dataset.view);
            document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
        });
    });

    document.getElementById('history-mrn-select').addEventListener('change', (e) => loadPatientHistory(e.target.value));
});

// --- NAVIGATION ---
function initNavigation() {
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            currentView = target;
            
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            tabSections.forEach(sec => {
                sec.classList.remove('active');
                if (sec.id === `tab-${target}`) sec.classList.add('active');
            });

            if (target === 'database') loadDatabase();
        });
    });
}

// --- FILE UPLOAD ---
function initFileUpload() {
    dropZone.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', (e) => {
        handleFiles(Array.from(e.target.files));
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('active');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('active');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('active');
        handleFiles(Array.from(e.dataTransfer.files));
    });
}

function handleFiles(files) {
    uploadedFiles = [...uploadedFiles, ...files];
    updateFileList();
    
    // Check if we have enough files to process
    const hasSeg = uploadedFiles.some(f => f.name.toLowerCase().includes('seg'));
    const hasAnat = uploadedFiles.some(f => f.name.toLowerCase().includes('t1'));
    
    btnProcess.disabled = !(hasSeg && hasAnat);
}

function updateFileList() {
    fileList.innerHTML = uploadedFiles.map(f => `
        <div class="file-item">
            <span>${f.name}</span>
            <span style="color: grey;">${(f.size / 1024 / 1024).toFixed(2)} MB</span>
        </div>
    `).join('');
}

// --- MRI PROCESSING ---
async function handleProcess() {
    if (uploadedFiles.length === 0) return;
    
    loadingOverlay.classList.remove('hidden');
    analysisPlaceholder.classList.add('hidden');
    analysisResults.classList.add('hidden');

    const formData = new FormData();
    formData.append('pat_id', document.getElementById('pat_id').value);
    uploadedFiles.forEach(file => {
        formData.append('files', file);
    });

    try {
        const response = await fetch(`${API_BASE}/process_mri`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error("Processing failed");

        analysisResult = await response.json();
        renderResults(analysisResult);
    } catch (error) {
        alert(`Error: ${error.message}`);
        analysisPlaceholder.classList.remove('hidden');
    } finally {
        loadingOverlay.classList.add('hidden');
    }
}

function renderResults(data) {
    analysisResults.classList.remove('hidden');
    
    document.getElementById('res-diagnosis').textContent = data.diagnosis;
    document.getElementById('res-location').textContent = data.location;
    document.getElementById('val-total').textContent = `${data.vols.total.toFixed(2)} cc`;
    document.getElementById('val-active').textContent = `${data.vols.enhancing.toFixed(2)} cc`;
    document.getElementById('val-edema').textContent = `${data.vols.edema.toFixed(2)} cc`;

    // Fetch and Show Report Preview
    updateReportPreview();

    // Render 3D Scene with Plotly
    const layout = {
        autosize: true,
        scene: {
            xaxis: { visible: false },
            yaxis: { visible: false },
            zaxis: { visible: false },
            bgcolor: 'black',
            aspectmode: 'data' // Keeps proportions correct
        },
        paper_bgcolor: 'black',
        margin: { l: 0, r: 0, b: 0, t: 0 },
        showlegend: true,
        legend: { font: { color: 'white' }, x: 0, y: 1 }
    };

    const config = { responsive: true, displayModeBar: false };
    Plotly.newPlot('3d-viewer', data.mesh_data, layout, config);
}

async function handleDownloadReport() {
    if (!analysisResult) return;

    const formData = new FormData();
    formData.append('patient_name', document.getElementById('pat_name').value);
    formData.append('mrn', document.getElementById('pat_id').value);
    formData.append('age', document.getElementById('pat_age').value);
    formData.append('diagnosis', analysisResult.diagnosis);
    formData.append('location', analysisResult.location);
    formData.append('total_vol_cc', analysisResult.vols.total);
    formData.append('necrosis_cc', analysisResult.vols.necrosis);
    formData.append('edema_cc', analysisResult.vols.edema);
    formData.append('active_tumor_cc', analysisResult.vols.enhancing);

    try {
        const response = await fetch(`${API_BASE}/generate_report`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error("Report generation failed");

        const htmlContent = await response.text();
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Medical_Report_${document.getElementById('pat_id').value}.html`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        alert("Failed to generate report.");
    }
}

async function updateReportPreview() {
    if (!analysisResult) return;

    const formData = new FormData();
    formData.append('patient_name', document.getElementById('pat_name').value);
    formData.append('mrn', document.getElementById('pat_id').value);
    formData.append('age', document.getElementById('pat_age').value);
    formData.append('diagnosis', analysisResult.diagnosis);
    formData.append('location', analysisResult.location);
    formData.append('total_vol_cc', analysisResult.vols.total);
    formData.append('necrosis_cc', analysisResult.vols.necrosis);
    formData.append('edema_cc', analysisResult.vols.edema);
    formData.append('active_tumor_cc', analysisResult.vols.enhancing);

    try {
        const response = await fetch(`${API_BASE}/generate_report`, {
            method: 'POST',
            body: formData
        });
        if (response.ok) {
            const htmlContent = await response.text();
            document.getElementById('report-preview-container').innerHTML = htmlContent;
        }
    } catch (err) {
        document.getElementById('report-preview-container').innerHTML = "<p>Failed to load report preview.</p>";
    }
}

// --- DATABASE OPERATIONS ---
async function handleSaveToDB() {
    if (!analysisResult) return;

    const formData = new FormData();
    formData.append('patient_name', document.getElementById('pat_name').value);
    formData.append('mrn', document.getElementById('pat_id').value);
    formData.append('age', document.getElementById('pat_age').value);
    formData.append('diagnosis', analysisResult.diagnosis);
    formData.append('location', analysisResult.location);
    formData.append('total_vol_cc', analysisResult.vols.total);
    formData.append('necrosis_cc', analysisResult.vols.necrosis);
    formData.append('edema_cc', analysisResult.vols.edema);
    formData.append('active_tumor_cc', analysisResult.vols.enhancing);

    try {
        const response = await fetch(`${API_BASE}/save_record`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            alert("✅ Record saved successfully and added to EHR.");
        }
    } catch (error) {
        alert("Failed to save record.");
    }
}

let allPatients = [];

async function loadDatabase() {
    try {
        const response = await fetch(`${API_BASE}/patients`);
        allPatients = await response.json();
        renderDatabaseTable(allPatients);
        updatePatientSelect(allPatients);
    } catch (error) {
        console.error("Failed to load records", error);
    }
}

function renderDatabaseTable(patients) {
    const tbody = document.getElementById('db-table-body');
    tbody.innerHTML = patients.map(p => `
        <tr>
            <td>${p.date_saved}</td>
            <td><strong>${p.patient_name}</strong></td>
            <td><code>${p.mrn}</code></td>
            <td>${p.diagnosis}</td>
            <td>${p.total_vol_cc.toFixed(2)}</td>
            <td>
                <div style="display: flex; gap: 5px;">
                    <button class="btn btn-primary" style="padding: 5px 10px; font-size: 11px;" onclick="viewHistory('${p.mrn}')">
                        <i data-lucide="eye" style="width:12px;height:12px;margin-right:5px;"></i> History
                    </button>
                    <button class="btn btn-outline" style="padding: 5px 10px; font-size: 11px;" onclick="downloadArchivedPdf(${p.id})">
                        <i data-lucide="download" style="width:12px;height:12px;margin-right:5px;"></i> PDF
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
    lucide.createIcons();
}

window.viewHistory = (mrn) => {
    switchDBView('history');
    document.querySelectorAll('.toggle-btn').forEach(b => {
        b.classList.remove('active');
        if (b.dataset.view === 'history') b.classList.add('active');
    });
    document.getElementById('history-mrn-select').value = mrn;
    loadPatientHistory(mrn);
};

function filterDatabase(query) {
    const filtered = allPatients.filter(p => 
        p.patient_name.toLowerCase().includes(query.toLowerCase()) || 
        p.mrn.toLowerCase().includes(query.toLowerCase())
    );
    renderDatabaseTable(filtered);
}

function switchDBView(view) {
    dbViewMode = view;
    document.getElementById('db-directory').classList.remove('active');
    document.getElementById('db-history').classList.remove('active');
    document.getElementById(`db-${view}`).classList.add('active');
}

function updatePatientSelect(patients) {
    const select = document.getElementById('history-mrn-select');
    const mrns = [...new Set(patients.map(p => p.mrn))];
    select.innerHTML = mrns.map(mrn => `<option value="${mrn}">${mrn}</option>`).join('');
}

async function loadPatientHistory(mrn) {
    try {
        const response = await fetch(`${API_BASE}/patients/${mrn}`);
        const history = await response.json();
        
        const tbody = document.getElementById('history-table-body');
        tbody.innerHTML = history.map(p => `
            <tr>
                <td>${p.date_saved}</td>
                <td>${p.total_vol_cc.toFixed(2)}</td>
                <td>${p.active_tumor_cc.toFixed(2)}</td>
                <td>${p.edema_cc.toFixed(2)}</td>
                <td>
                    <button class="btn btn-outline" style="padding: 2px 8px; font-size: 10px;" onclick="downloadArchivedPdf(${p.id})">
                        <i data-lucide="download" style="width:10px;height:10px;"></i>
                    </button>
                </td>
            </tr>
        `).join('');
        lucide.createIcons();

        renderProgressionChart(history);
    } catch (error) {
        console.error("Failed to load history", error);
    }
}

function renderProgressionChart(history) {
    const trace1 = {
        x: history.map(h => h.date_saved),
        y: history.map(h => h.total_vol_cc),
        name: 'Total Volume',
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: '#00E5FF', width: 2 },
        marker: { size: 8 }
    };

    const trace2 = {
        x: history.map(h => h.date_saved),
        y: history.map(h => h.active_tumor_cc),
        name: 'Active Core',
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: '#FF3B30', width: 2 },
        marker: { size: 8 }
    };

    const layout = {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: 'white' },
        margin: { l: 40, r: 20, b: 40, t: 20 },
        xaxis: { gridcolor: 'rgba(255,255,255,0.1)' },
        yaxis: { gridcolor: 'rgba(255,255,255,0.1)' },
        legend: { orientation: 'h', y: -0.2 }
    };

    Plotly.newPlot('progression-chart', [trace1, trace2], layout);
}

window.downloadArchivedPdf = (recordId) => {
    window.open(`${API_BASE}/download_pdf/${recordId}`, '_blank');
};

// --- UTILS ---
function resetApp() {
    uploadedFiles = [];
    updateFileList();
    btnProcess.disabled = true;
    analysisResult = null;
    analysisResults.classList.add('hidden');
    analysisPlaceholder.classList.remove('hidden');
    document.getElementById('pat_name').value = "";
    document.getElementById('pat_id').value = "";
    document.getElementById('pat_age').value = 0;
}

function initDatabase() {
    // Initial load happens when switching to tab
}
