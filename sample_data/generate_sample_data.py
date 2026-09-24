"""Generate realistic RMS-style sample input files.

Lets you exercise the whole pipeline (and the Streamlit app) without touching
the live RMS portal. Replace these with the real RMS exports in production.
"""
import random
from pathlib import Path

import pandas as pd

random.seed(7)
OUT = Path(__file__).resolve().parent

FIRST = ["Sakshi", "Meera", "Rahul", "Priya", "Amit", "Neha", "Vikram", "Anjali", "Rohit",
         "Kavita", "Suresh", "Deepa", "Manish", "Pooja", "Arun", "Shreya", "Nitin", "Ritu",
         "Sanjay", "Divya", "Harish", "Swati", "Rajesh", "Anita", "Varun", "Sneha", "Ajay",
         "Meenakshi", "Karan", "Nisha"]
LAST = ["Nagpal", "Luhar", "Sharma", "Verma", "Gupta", "Singh", "Mehta", "Joshi", "Nair",
        "Reddy", "Iyer", "Patel", "Chauhan", "Bansal", "Kapoor", "Rao", "Das", "Bose",
        "Mishra", "Yadav"]
DEPTS = ["IT", "Sales", "Finance", "HR", "Operations", "Training", "Marketing", "Support"]
DESIGS = ["Software Engineer", "Senior Software Engineer", "Team Lead", "Manager", "Executive",
          "Consultant", "Assistant Manager", "Director"]
LOCS = ["Delhi", "Gurgaon", "Goa", "Chennai", "Dehradun", "Bangalore", "Noida", "Mumbai", "Pune"]


def write_html_xls(path, title, df):
    """Mimic the RMS export: an HTML page with a small title table + the data table."""
    title_html = pd.DataFrame(
        [["KOENIG SOLUTIONS PVT LTD", "", ""], [title, "", ""], ["", "", ""]]
    ).to_html(index=False, header=False, border=1)
    path.write_text(
        "<html><body>" + title_html + df.to_html(index=False, border=1) + "</body></html>",
        encoding="utf-8",
    )


def build_salary(n=150):
    rows, uans = [], set()
    for i in range(n):
        while True:
            uan = "10" + "".join(random.choice("0123456789") for _ in range(10))
            if uan not in uans:
                uans.add(uan)
                break
        salary = float(random.randrange(28000, 180000, 500))
        pf = round(min(1800.0, salary * 0.12), 2)
        vpf = round(random.choice([0.0, 0.0, 0.0, 500.0, 1000.0]), 2)
        tds = round(salary * random.choice([0.0, 0.05, 0.10, 0.15]), 2)
        net = round(salary - pf - vpf - tds, 2)
        rows.append({
            "EmpCode": 3001 + i,
            "EmployeeName": f"{random.choice(FIRST)} {random.choice(LAST)}",
            "Department": random.choice(DEPTS),
            "Designation": random.choice(DESIGS),
            "UAN": uan,
            "BaseLocation": random.choice(LOCS),
            "Salary": salary, "PF": pf, "VPF": vpf, "TDS": tds,
            "NetPayable": net, "NetPayable1": net,
        })
    return pd.DataFrame(rows)


def main():
    salary = build_salary()
    salary["EPF"] = salary["PF"] + salary["VPF"]
    codes = salary["EmpCode"].tolist()

    # ---------------- TDS sheet ----------------
    tds = salary[["EmpCode", "EmployeeName", "TDS"]].rename(
        columns={"EmpCode": "Employee Code", "EmployeeName": "Name", "TDS": "Salary TDS"}
    )
    tds = tds[~tds["Employee Code"].isin(random.sample(codes, 5))]          # missing TDS
    bump = random.sample(codes, 8)
    tds.loc[tds["Employee Code"].isin(bump), "Salary TDS"] += 250.50        # TDS mismatch
    with pd.ExcelWriter(OUT / "Update TDS.xlsx", engine="openpyxl") as w:
        pd.DataFrame([["TDS REPORT", "", ""]]).to_excel(w, sheet_name="TDS", index=False, header=False)
        tds.to_excel(w, sheet_name="TDS", index=False, startrow=1)

    # ---------------- Bank SOA ----------------
    bank_src = salary[~salary["EmpCode"].isin(random.sample(codes, 10))]   # unpaid
    bank_src = bank_src.copy()
    short = random.sample(bank_src["EmpCode"].tolist(), 5)
    bank_src.loc[bank_src["EmpCode"].isin(short), "NetPayable"] -= 1500.0  # underpaid
    bank = pd.DataFrame({
        "Date": ["15-Nov-2025"] * len(bank_src),
        "TransactionID": [f"TXN{i:07d}" for i in range(1, len(bank_src) + 1)],
        "Employee": [f"{n}-{c}" for n, c in zip(bank_src["EmployeeName"], bank_src["EmpCode"])],
        "Narration": "Salary Payment",
        "Amount": [f"{a:,.2f}" for a in bank_src["NetPayable"]],
    })
    write_html_xls(OUT / "BankBookEntrySalaryUploaded_23-Sep-2026.xls",
                   "BANK BOOK ENTRY - SALARY UPLOADED", bank)

    # ---------------- EPF sheet ----------------
    epf = salary[["EmpCode", "UAN", "EPF"]].rename(columns={"EPF": "EPF Amount"})
    epf = epf[~epf["EmpCode"].isin(random.sample(codes, 4))]            # missing EPF
    bump2 = random.sample(epf["EmpCode"].tolist(), 7)
    epf.loc[epf["EmpCode"].isin(bump2), "EPF Amount"] += 200.0          # EPF mismatch
    epf.to_excel(OUT / "epf_nov_2025.xlsx", index=False)

    # ---------------- Salary sheet (HTML .xls, like RMS) ----------------
    write_html_xls(OUT / "Salay_Sheet_November_2025.xls",
                   "SALARY SHEET - NOVEMBER 2025", salary.drop(columns=["EPF"]))

    for f in sorted(OUT.glob("*")):
        if f.suffix in (".xls", ".xlsx"):
            print(f"  {f.name:<45} {f.stat().st_size:>10,} bytes")


if __name__ == "__main__":
    main()
