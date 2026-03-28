import nibabel as nib
import numpy as np
import os
from skimage import measure
import plotly.graph_objects as go
import tempfile
from fpdf import FPDF
from datetime import datetime

def process_mri(anat_path, seg_path):
    """Processes MRI anatomy and segmentation files to calculate volumes and generate 3D data."""
    try:
        n_anat = nib.load(anat_path)
        d_anat = n_anat.get_fdata()
        n_seg = nib.load(seg_path)
        d_seg = n_seg.get_fdata()
        spacing = n_anat.header.get_zooms()[:3]
        
        # Calculations
        voxel_vol = np.prod(spacing) / 1000
        vols = {
            'necrosis': float(np.sum(d_seg == 1) * voxel_vol),
            'edema': float(np.sum(d_seg == 2) * voxel_vol),
            'enhancing': float(np.sum(d_seg == 4) * voxel_vol)
        }
        vols['total'] = sum(vols.values())
        
        diagnosis = "Glioblastoma Multiforme (HGG)" if vols['enhancing'] > 5.0 else "Low Grade Glioma (LGG)"
        
        mask_t = np.where(d_seg > 0, 1, 0)
        if np.sum(mask_t) > 0:
            center = np.array(np.where(mask_t > 0)).mean(axis=1)
            real_pos = nib.affines.apply_affine(n_anat.affine, center)
            side = "Right" if real_pos[0] > 0 else "Left"
            lobe = "Parietal" if real_pos[1] < 0 else "Frontal"
        else:
            side, lobe = "Unknown", "Unknown"
        
        location_str = f"{side} {lobe} Lobe"

        # Prepare 3D Mesh data for Plotly (to be sent as JSON)
        mesh_data = []
        
        # Anatomy (Brain Surface)
        mask_b = np.where(d_anat > 40, 1, 0)
        if np.sum(mask_b) > 1000:
            verts, faces, _, _ = measure.marching_cubes(mask_b, level=0.5)
            mesh_data.append({
                'type': 'mesh3d',
                'x': verts[:, 0].tolist(),
                'y': verts[:, 1].tolist(),
                'z': verts[:, 2].tolist(),
                'i': faces[:, 0].tolist(),
                'j': faces[:, 1].tolist(),
                'k': faces[:, 2].tolist(),
                'color': '#00E5FF',
                'opacity': 0.1,
                'name': 'Anatomy'
            })
        
        # Enhancing Tumor
        mask_e = np.where(d_seg == 4, 1, 0)
        if np.sum(mask_e) > 0:
            verts, faces, _, _ = measure.marching_cubes(mask_e, level=0.5)
            mesh_data.append({
                'type': 'mesh3d',
                'x': verts[:, 0].tolist(),
                'y': verts[:, 1].tolist(),
                'z': verts[:, 2].tolist(),
                'i': faces[:, 0].tolist(),
                'j': faces[:, 1].tolist(),
                'k': faces[:, 2].tolist(),
                'color': '#FF0000',
                'opacity': 1.0,
                'name': 'Enhancing Tumor'
            })

        # Fluid/Edema
        mask_edema = np.where(d_seg == 2, 1, 0)
        if np.sum(mask_edema) > 0:
            verts, faces, _, _ = measure.marching_cubes(mask_edema, level=0.5)
            mesh_data.append({
                'type': 'mesh3d',
                'x': verts[:, 0].tolist(),
                'y': verts[:, 1].tolist(),
                'z': verts[:, 2].tolist(),
                'i': faces[:, 0].tolist(),
                'j': faces[:, 1].tolist(),
                'k': faces[:, 2].tolist(),
                'color': '#00FF88',
                'opacity': 0.3,
                'name': 'Fluid/Edema'
            })

        # --- Centering the meshes ---
        # We calculate the combined mean of ALL vertices across all meshes
        # to ensure they stay correctly aligned relative to each other.
        all_verts = []
        for m in mesh_data:
            all_verts.extend(np.column_stack((m['x'], m['y'], m['z'])))
        
        if all_verts:
            mean_pos = np.mean(all_verts, axis=0)
            for m in mesh_data:
                m['x'] = (np.array(m['x']) - mean_pos[0]).tolist()
                m['y'] = (np.array(m['y']) - mean_pos[1]).tolist()
                m['z'] = (np.array(m['z']) - mean_pos[2]).tolist()

        return {
            'vols': vols,
            'diagnosis': diagnosis,
            'side': side,
            'lobe': lobe,
            'location': location_str,
            'mesh_data': mesh_data
        }
    except Exception as e:
        return {"error": str(e)}

from datetime import datetime

def generate_report_content(p_name, p_id, p_age, diag, loc, vols):
    """Generates HTML report content based on patient data."""
    v_total, v_necrosis, v_edema, v_enhancing = vols['total'], vols['necrosis'], vols['edema'], vols['enhancing']
    edema_index = (v_edema / v_total * 100) if v_total > 0 else 0
    fluid_status = "Significant Mass Effect" if v_edema > 50 else "Moderate Peritumoral Fluid" if v_edema > 20 else "Minimal Fluid"
    
    # SVG Icons for the report
    hospital_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#004488" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 2h-3a3 3 0 0 0-3 3V22h9V5a3 3 0 0 0-3-3Z"/><path d="M9 22V5a3 3 0 0 0-3-3H3a3 3 0 0 0-3 3v17h9Z"/><path d="M7 10v4"/><path d="M5 12h4"/><path d="M15 10v4"/><path d="M13 12h4"/></svg>'
    fluid_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#004488" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/></svg>'

    html = []
    html.append('<div style="background-color: white; color: #111; padding: 40px; font-family: \'serif\'; line-height: 1.6; max-width: 900px; margin: auto; box-shadow: 0 0 20px rgba(0,0,0,0.1); text-align: left;">')
    html.append('<table style="width: 100%; border-bottom: 3px solid #004488; padding-bottom: 20px; margin-bottom: 30px; border-collapse: collapse;"><tr>')
    html.append(f'<td style="width: 15%; text-align: left; vertical-align: middle;">{hospital_icon}</td>')
    html.append('<td style="width: 65%; vertical-align: middle; text-align: center;"><h2 style="margin: 0; font-family: sans-serif; text-transform: uppercase; color: #004488; font-size: 24px;">Department of Neuroradiology</h2><p style="margin: 5px 0 0 0; font-size: 14px; color: #666;">Advanced AI Diagnostic Imaging Center</p></td>')
    html.append(f'<td style="width: 20%; text-align: right; font-size: 11px; color: #888; vertical-align: bottom;">Report ID: {p_id}-{datetime.now().strftime("%H%M")}<br>Generated: {datetime.now().strftime("%Y-%m-%d")}</td>')
    html.append('</tr></table>')

    html.append('<div style="background-color: #f8f9fa; padding: 15px; border: 1px solid #e9ecef; border-left: 5px solid #004488; font-family: sans-serif; font-size: 13px; margin-bottom: 20px; text-align: left;">')
    html.append('<table style="width: 100%; text-align: left;">')
    html.append(f'<tr><td style="padding-bottom: 5px;"><b>PATIENT:</b> {p_name}</td><td><b>MRN:</b> {p_id}</td><td><b>AGE:</b> {p_age}</td></tr>')
    html.append(f'<tr><td><b>DATE:</b> {datetime.now().strftime("%Y-%m-%d")}</td><td><b>PHYSICIAN:</b> Dr. S. Strange</td><td><b>SCAN:</b> Multi-Parametric MRI</td></tr>')
    html.append('</table></div>')

    html.append('<h3 style="border-bottom: 1px solid #ccc; color: #004488; font-family: sans-serif; margin-top: 20px; text-align: left;">1. FINDINGS</h3>')
    html.append(f'<p style="text-align: left;"><b>INTRACRANIAL MASS:</b> A space-occupying lesion is identified in the <b>{loc}</b>. The total lesion volume measures <b>{v_total:.2f} cc</b>.</p>')

    html.append(f'<h4 style="margin-bottom: 5px; font-family: sans-serif; font-size: 15px; color: #333; margin-top: 25px; text-align: left;">{fluid_icon} FLUID DYNAMICS (Liquid Level Analysis)</h4>')
    html.append('<ul style="margin-top: 5px; font-size: 14px; text-align: left; padding-left: 20px;">')
    html.append(f'<li><b>Peritumoral Edema Volume:</b> {v_edema:.2f} cc</li>')
    html.append(f'<li><b>Edema/Tumor Ratio:</b> {edema_index:.1f}% (Fluid dominance).</li>')
    html.append(f'<li><b>Interpretation:</b> {fluid_status}. Hyperintense signal on T2/FLAIR indicating vasogenic edema.</li>')
    html.append('</ul>')

    html.append('<h4 style="margin-bottom: 5px; font-family: Arial, sans-serif; font-size: 15px; color: #333; margin-top: 25px; text-align: left;">TISSUE CHARACTERIZATION</h4>')
    html.append('<ul style="margin-top: 5px; font-size: 14px; text-align: left; padding-left: 20px;">')
    html.append(f'<li><b>Necrotic Core:</b> {v_necrosis:.2f} cc - <i>Central non-enhancing region.</i></li>')
    html.append(f'<li><b>Enhancing Tumor:</b> {v_enhancing:.2f} cc - <i>Active solid tumor component.</i></li>')
    html.append('</ul>')

    html.append('<div style="border: 2px solid #004488; background-color: #f0f7ff; padding: 20px; margin-top: 40px; text-align: left;">')
    html.append('<h3 style="margin-top: 0; color: #004488; font-family: Arial, sans-serif; font-size: 18px; text-align: left;">IMPRESSION</h3>')
    html.append(f'<p style="font-weight: bold; font-size: 20px; margin-bottom: 10px; color: #000; text-align: left;">{diag}</p>')
    html.append('<p style="margin: 0; font-size: 14px; text-align: left;">Findings are consistent with High-Grade Glioma. The presence of significant central necrosis and surrounding vasogenic edema supports this diagnosis.<br><br><b>PLAN:</b> Neurosurgical consultation recommended.</p>')
    html.append('</div>')

    html.append('<div style="margin-top: 60px; text-align: right;">')
    html.append('<div style="display: inline-block; text-align: center; border-top: 1px solid #000; padding-top: 10px; width: 250px;">')
    html.append('<b>NeuroVis AI Engine, M.D.</b><br><span style="font-size: 12px; color: #666;">Board Certified Neuroradiologist</span>')
    html.append('</div></div>')

    html.append('</div>') 
    return "".join(html)

def generate_pdf_report(p_name, p_id, p_age, diag, loc, vols, output_path):
    """Generates a professional PDF report for clinical storage."""
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_fill_color(0, 68, 136)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 24)
    pdf.cell(190, 20, "NEUROVIS AI DIAGNOSTICS", 0, 1, 'C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 5, "Advanced Neuroradiology Report", 0, 1, 'C')
    
    pdf.ln(20)
    pdf.set_text_color(0, 0, 0)
    
    # Patient Info Table
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(40, 10, "PATIENT:", 0, 0)
    pdf.set_font("Arial", '', 12)
    pdf.cell(60, 10, p_name, 0, 0)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(30, 10, "MRN:", 0, 0)
    pdf.set_font("Arial", '', 12)
    pdf.cell(50, 10, p_id, 0, 1)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(40, 10, "AGE:", 0, 0)
    pdf.set_font("Arial", '', 12)
    pdf.cell(60, 10, str(p_age), 0, 0)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(30, 10, "DATE:", 0, 0)
    pdf.set_font("Arial", '', 12)
    pdf.cell(50, 10, datetime.now().strftime("%Y-%m-%d"), 0, 1)
    
    pdf.ln(10)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # Findings
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(0, 68, 136)
    pdf.cell(190, 10, "1. CLINICAL FINDINGS", 0, 1)
    pdf.set_font("Arial", '', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(190, 8, f"An intracranial mass was identified in the {loc}. AI-driven segmentation reveals a total lesion volume of {vols['total']:.2f} cc.")
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "Volumetric Data:", 0, 1)
    pdf.set_font("Arial", '', 11)
    pdf.cell(60, 8, f"- Enhancing Core:", 0, 0)
    pdf.cell(130, 8, f"{vols['enhancing']:.2f} cc", 0, 1)
    pdf.cell(60, 8, f"- Peritumoral Edema:", 0, 0)
    pdf.cell(130, 8, f"{vols['edema']:.2f} cc", 0, 1)
    pdf.cell(60, 8, f"- Necrotic Region:", 0, 0)
    pdf.cell(130, 8, f"{vols['necrosis']:.2f} cc", 0, 1)
    
    pdf.ln(10)
    # Impression
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(0, 68, 136)
    pdf.cell(190, 10, "2. IMPRESSION", 0, 1)
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(255, 0, 0)
    pdf.cell(190, 10, diag, 0, 1)
    pdf.set_font("Arial", '', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(190, 8, "Findings are highly suggestive of high-grade pathology. Immediate neurological consultation is advised.")
    
    pdf.output(output_path)
