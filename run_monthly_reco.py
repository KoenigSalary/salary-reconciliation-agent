import logging
from main import SalaryReconciliationAgent

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    agent = SalaryReconciliationAgent()
    agent.run_full_reconciliation()
