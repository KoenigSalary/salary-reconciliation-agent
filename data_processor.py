"""
Data Processor Module
Handles processing of salary, TDS, bank, and EPF data files
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
import re

from config import Config

logger = logging.getLogger(__name__)


class DataProcessor:
    @staticmethod
    def read_excel_file(file_path, **kwargs):
        """
        Read Excel file - handles real Excel, HTML-disguised .xls, and TSV files.
        """
        logger.info(f"Reading file: {file_path}")
        
        try:
            # Try reading as real Excel first
            df = pd.read_excel(file_path, **kwargs)
            logger.info(f"Read as Excel: {len(df)} rows")
            return df
        except Exception as e:
            logger.debug(f"Not real Excel, trying alternatives: {e}")
            
            try:
                # Try reading as HTML table
                tables = pd.read_html(file_path, **kwargs)
                
                if not tables:
                    raise ValueError("No tables found")
                
                # Return the largest table by area
                largest_table = max(tables, key=lambda t: len(t) * len(t.columns))
                logger.info(f"Read as HTML table: {len(largest_table)} rows, {len(largest_table.columns)} cols")
                return largest_table
                
            except Exception as e2:
                logger.debug(f"Not HTML, trying TSV: {e2}")
                
                try:
                    # Try reading as TSV (tab-separated)
                    df = pd.read_csv(file_path, sep='\t', **kwargs)
                    logger.info(f"Read as TSV: {len(df)} rows, {len(df.columns)} cols")
                    return df
                except Exception as e3:
                    logger.error(f"Failed all read methods: Excel, HTML, TSV")
                    raise ValueError(f"Could not read file: {e3}")

    @staticmethod
    def extract_employee_id_from_name(name_str):
        """
        Extract employee ID from 'Name-ID' format.
        Examples:
          'Sakshi Nagpal-3353' -> '3353'
          'Meera Luhar-3828' -> '3828'
          'John Doe' -> None
        """
        if pd.isna(name_str):
            return None
        
        name_str = str(name_str).strip()
        match = re.search(r'-(\d+)$', name_str)
        return match.group(1) if match else None

    @staticmethod
    def process_salary_sheet(file_path):
        """
        Salary sheet from RMS is HTML-exported .xls containing 2 tables:
        - Table 0: title (3x4)
        - Table 1: real data (~554x49)
        Our read_excel_file() already returns the biggest table.
        """
        logger.info(f"Processing salary sheet: {file_path}")

        # RMS Salary sheet is HTML table
        df = DataProcessor.read_excel_file(file_path)
        df.columns = [str(c).strip() for c in df.columns]

        # Convert to numeric where needed
        for col in ["Salary", "PF", "VPF", "TDS", "NetPayable", "NetPayable1"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        salary_data = pd.DataFrame({
            "EmpCode": df["EmpCode"].astype(str).str.strip(),
            "EmployeeName": df.get("EmployeeName"),
            "Department": df.get("Department"),
            "Designation": df.get("Designation"),
            "UAN": df.get("UAN"),
            "Location": df.get("BaseLocation"),
        })

        # Gross Salary = Salary column
        salary_data["GrossSalary"] = df["Salary"].fillna(0) if "Salary" in df.columns else 0

        # Clean UAN
        salary_data["UAN"] = (
            salary_data["UAN"]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
        )
        salary_data["UAN"] = salary_data["UAN"].replace({"nan": None, "None": None, "": None})

        # EPF = PF + VPF
        pf = df["PF"].fillna(0) if "PF" in df.columns else 0
        vpf = df["VPF"].fillna(0) if "VPF" in df.columns else 0
        salary_data["EPF"] = pf + vpf

        # Salary sheet TDS
        salary_data["TDS"] = df["TDS"].fillna(0) if "TDS" in df.columns else 0

        # FinalNetPayable formula
        net1 = df["NetPayable"].fillna(0) if "NetPayable" in df.columns else 0
        net2 = df["NetPayable1"].fillna(0) if "NetPayable1" in df.columns else 0
        salary_data["FinalNetPayable"] = net1.where(net1 == net2, net2)

        # Clean EmpCode
        salary_data = salary_data[
            salary_data["EmpCode"].notna()
            & (salary_data["EmpCode"] != "")
            & (salary_data["EmpCode"] != "nan")
        ]

        # Check for duplicates
        original_count = len(salary_data)
        duplicates = salary_data[salary_data.duplicated(subset=['EmpCode'], keep=False)]
        if len(duplicates) > 0:
            logger.warning(f"Found {len(duplicates)} duplicate EmpCodes in salary sheet!")
            salary_data = salary_data.drop_duplicates(subset=['EmpCode'], keep='first')
            logger.warning(f"Removed {original_count - len(salary_data)} duplicate rows")

        # Branch mapping
        salary_data["Branch"] = salary_data["Location"].apply(Config.map_branch)

        logger.info(f"Processed {len(salary_data)} employees from salary sheet")
        return salary_data

    @staticmethod
    def process_tds_sheet(file_path):
        logger.info(f"Processing TDS sheet: {file_path}")
        df = DataProcessor.read_excel_file(file_path, skiprows=1)

        tds_data = pd.DataFrame({
            "EmpCode": df["Employee Code"].astype(str).str.strip(),
            "EmployeeName": df.get("Name"),
            "TDS_Amount": pd.to_numeric(df.get("Salary TDS", 0), errors="coerce"),
        })

        tds_data = tds_data[tds_data["EmpCode"].notna()]
        tds_data = tds_data[tds_data["EmpCode"] != ""]
        tds_data = tds_data[tds_data["EmpCode"] != "nan"]

        logger.info(f"Processed {len(tds_data)} records from TDS sheet")
        return tds_data

    @staticmethod
    def process_bank_soa(file_path):
        """
        Process Bank SOA - aggregates multiple payments per employee.
        """
        logger.info(f"Processing Bank SOA: {file_path}")
        df = DataProcessor.read_excel_file(file_path)

        df.columns = [str(c).strip() for c in df.columns]

        if "Employee" in df.columns:
            df["EmpCode"] = df["Employee"].apply(DataProcessor.extract_employee_id_from_name)
        else:
            df["EmpCode"] = None

        # Handle comma-formatted amounts
        if "Amount" in df.columns:
            df["Amount_Clean"] = df["Amount"].astype(str).str.replace(",", "").str.strip()
            amount_numeric = pd.to_numeric(df["Amount_Clean"], errors="coerce")
        else:
            amount_numeric = 0

        bank_data = pd.DataFrame({
            "EmpCode": df["EmpCode"].astype(str).str.strip(),
            "EmployeeName": df.get("Employee"),
            "BankPayment": amount_numeric,
            "PaymentDate": df.get("Date"),
            "TransactionID": df.get("TransactionID"),
        })

        bank_data = bank_data[bank_data["EmpCode"].notna()]
        bank_data = bank_data[bank_data["EmpCode"] != ""]
        bank_data = bank_data[bank_data["EmpCode"] != "nan"]
        bank_data = bank_data[bank_data["EmpCode"] != "None"]
        bank_data = bank_data[bank_data["BankPayment"].notna()]
        bank_data = bank_data[bank_data["BankPayment"] > 0]

        logger.info(f"Filtered {len(bank_data)} valid transactions")

        # Aggregate before returning
        bank_agg = bank_data.groupby("EmpCode", as_index=False).agg(
            BankPayment=("BankPayment", "sum"),
            EmployeeName=("EmployeeName", "first"),
            PaymentDate=("PaymentDate", "max"),
            TransactionID=("TransactionID", lambda x: ", ".join(pd.Series(x).dropna().astype(str).unique())[:500]),
        )

        logger.info(f"Bank aggregated: {len(bank_data)} txns → {len(bank_agg)} employees")
        return bank_agg

    @staticmethod
    def process_epf_sheet(file_path):
        logger.info(f"Processing EPF sheet: {file_path}")
        
        try:
            df = DataProcessor.read_excel_file(file_path)
        except Exception as e:
            logger.error(f"Failed to read EPF file: {e}")
            return pd.DataFrame(columns=["UAN", "EPF_Amount"])

        df.columns = [str(c).strip().lower() for c in df.columns]

        uan_col = None
        for col in df.columns:
            if 'uan' in col:
                uan_col = col
                break

        epf_col = None
        for col in df.columns:
            if 'epf' in col and 'amount' in col:
                epf_col = col
                break
        if not epf_col:
            for col in df.columns:
                if 'amount' in col:
                    epf_col = col
                    break

        if not uan_col or not epf_col:
            logger.error(f"EPF missing columns. Found: {df.columns.tolist()}")
            return pd.DataFrame(columns=["UAN", "EPF_Amount"])

        epf_data = pd.DataFrame({
            "UAN": df[uan_col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True),
            "EPF_Amount": pd.to_numeric(df[epf_col], errors="coerce"),
        })

        epf_data["UAN"] = epf_data["UAN"].replace({"nan": None, "None": None, "": None})
        epf_data = epf_data[epf_data["UAN"].notna()]
        epf_data = epf_data[epf_data["EPF_Amount"].notna()]

        logger.info(f"Processed {len(epf_data)} EPF records")
        return epf_data
