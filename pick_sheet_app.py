import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime
from PyPDF2 import PdfMerger
import os

# Define column widths for the ToDo table for easier adjustments
DESCRIPTION_WIDTH = 60
NOTES_WIDTH = 80
COMPLETE_WIDTH = 30
PICKED_WIDTH = 20

class PickSheetPDF(FPDF):
    def __init__(self, install_date):
        super().__init__()
        # Ensure installation date is a string and only take the date part
        self.install_date = str(install_date).split(" ")[0] if install_date else "Unknown"

    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, f"Job Pick Sheet for {self.install_date}", ln=True, align="C")

    def add_job_info(self, last_name, po, contract_date, installer):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, f"Customer: {last_name}", ln=True)
        self.cell(0, 10, f"PO: {po}", ln=True)
        self.cell(0, 10, f"Contract Date: {contract_date}", ln=True)
        self.set_font("Arial", "", 12)
        self.cell(0, 10, f"Installer: {installer}", ln=True)
        self.ln(5)

    def add_product_table(self, data):
        # Header for the product table
        self.set_font("Arial", "B", 12)
        self.cell(40, 10, "Product ID", 1)
        self.cell(40, 10, "Color", 1)
        self.cell(30, 10, "Qty", 1)
        self.cell(40, 10, "Dock Location", 1)
        self.cell(20, 10, "Picked", 1)
        self.ln()
        
        # Table rows for products
        self.set_font("Arial", "", 12)
        for row in data:
            self.cell(40, 10, str(row.get("Productid", "")), 1)
            self.cell(40, 10, str(row.get("Color", "")), 1)
            self.cell(30, 10, str(row.get("Qty", "")), 1)
            self.cell(40, 10, str(row.get("Dock_Location", "")), 1)
            self.cell(20, 10, "", 1)
            self.ln()
        self.ln(10)

    def add_todo_table(self, data):
        # Header for the ToDo table
        self.set_font("Arial", "B", 12)
        self.cell(DESCRIPTION_WIDTH, 10, "Description", 1)
        self.cell(NOTES_WIDTH, 10, "Notes", 1)
        self.cell(COMPLETE_WIDTH, 10, "Completed", 1)
        self.cell(PICKED_WIDTH, 10, "Picked", 1)
        self.ln()
        
        self.set_font("Arial", "", 12)
        for row in data:
            description = str(row.get("Description", ""))
            notes = str(row.get("Notes", ""))
            complete_date = row.get("Complete_Date", "")
            # Parse the complete date if possible
            if isinstance(complete_date, str) and complete_date:
                try:
                    complete_date = datetime.strptime(complete_date, "%m/%d/%Y %I:%M:%S %p").strftime("%m/%d/%Y")
                except ValueError:
                    complete_date = complete_date.split(" ")[0]

            # Get the starting position for the row
            start_x = self.get_x()
            start_y = self.get_y()

            # Use multi_cell in split_only mode to measure the height needed for the Notes cell
            notes_lines = self.multi_cell(NOTES_WIDTH, 10, notes, border=0, align="L", split_only=True)
            max_height = 10 * len(notes_lines) if notes_lines else 10

            # Draw the Description cell
            self.set_xy(start_x, start_y)
            self.cell(DESCRIPTION_WIDTH, max_height, description, border=1)

            # Draw the Notes cell with text wrapping
            self.set_xy(start_x + DESCRIPTION_WIDTH, start_y)
            self.multi_cell(NOTES_WIDTH, 10, notes, border=1)

            # Draw the Completed and Picked cells, keeping the same height
            self.set_xy(start_x + DESCRIPTION_WIDTH + NOTES_WIDTH, start_y)
            self.cell(COMPLETE_WIDTH, max_height, complete_date, border=1)
            self.cell(PICKED_WIDTH, max_height, "", border=1)

            # Move cursor to next row
            self.ln(max_height)
        self.ln(10)

    def add_signature_section(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "Sign-Offs", ln=True)
        self.set_font("Arial", "", 12)
        self.cell(0, 10, "Picked By: ___________________________", ln=True)
        self.cell(0, 10, "Confirmed By: ________________________", ln=True)
        self.cell(0, 10, "Installer Sign Off: __________________", ln=True)

def generate_pick_sheets(df):
    pdf_files = []
    os.makedirs("output", exist_ok=True)

    # Group jobs by PO (Purchase Order) - handle both "PO" and "PO#" column names
    po_column = "PO#" if "PO#" in df.columns else "PO"
    
    for po, job_df in df.groupby(po_column):
        # Replace NaN values with empty strings for safety
        job_df = job_df.replace({np.nan: ""})
        # Extract installation date from the first row
        install_date = str(job_df.iloc[0].get("InstallationDate", "Unknown")).split(" ")[0]

        pdf = PickSheetPDF(install_date)
        pdf.add_page()

        # Separate product and ToDo data
        adp_df = job_df[job_df["Productid"] != ""]
        todo_df = job_df[job_df["Description"] != ""]

        # Use safe dictionary access for job info fields
        first_row = job_df.iloc[0]
        pdf.add_job_info(
            first_row.get("LastName", "N/A"),
            po,
            first_row.get("ContractDate", "N/A"),
            first_row.get("Installer", "N/A")
        )

        if not adp_df.empty:
            pdf.add_product_table(adp_df.to_dict(orient="records"))
        if not todo_df.empty:
            # Pre-process the ToDo data: simplify the Complete_Date field
            todo_data = todo_df.to_dict(orient="records")
            for row in todo_data:
                row["Complete_Date"] = (str(row.get("Complete_Date", ""))
                                        .split(" ")[0] if row.get("Complete_Date") else "")
            pdf.add_todo_table(todo_data)

        pdf.add_signature_section()

        # Save the PDF for this PO and add it to the list
        pdf_path = f"output/job_pick_sheet_PO_{po}.pdf"
        pdf.output(pdf_path)
        pdf_files.append(pdf_path)

    return pdf_files

def merge_pdfs(pdf_list, output_filename):
    merger = PdfMerger()
    for pdf in pdf_list:
        merger.append(pdf)
    merger.write(output_filename)
    merger.close()

# Streamlit app interface
st.title("Job Pick Sheet Generator")
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.success("File uploaded successfully. Generating pick sheets...")
    pdf_list = generate_pick_sheets(df)
    merged_file = "output/all_jobs_pick_sheet_combined.pdf"
    merge_pdfs(pdf_list, merged_file)
    with open(merged_file, "rb") as f:
        st.download_button("Download Combined PDF", f, file_name="All_Pick_Sheets.pdf")
