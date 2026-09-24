"""
Scheduler Module
Schedules the agent to run on 16th and 18th of every month
"""

import schedule
import time
import logging
from datetime import datetime
from main import SalaryReconciliationAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def job_epf_reminder():
    """Job to send EPF reminder on 16th"""
    logger.info("Executing EPF Reminder Job")
    agent = SalaryReconciliationAgent()
    agent.send_epf_reminder()

def job_reconciliation():
    """Job to run full reconciliation on 18th"""
    logger.info("Executing Reconciliation Job")
    agent = SalaryReconciliationAgent()
    agent.run_full_reconciliation()

def check_and_run_jobs():
    """Check current date and run appropriate job"""
    today = datetime.now().day
    
    if today == 16:
        # Check if already run today
        if not hasattr(check_and_run_jobs, 'last_reminder_date') or \
           check_and_run_jobs.last_reminder_date != datetime.now().date():
            logger.info("16th of month - Running EPF Reminder")
            job_epf_reminder()
            check_and_run_jobs.last_reminder_date = datetime.now().date()
    
    elif today == 18:
        # Check if already run today
        if not hasattr(check_and_run_jobs, 'last_recon_date') or \
           check_and_run_jobs.last_recon_date != datetime.now().date():
            logger.info("18th of month - Running Reconciliation")
            job_reconciliation()
            check_and_run_jobs.last_recon_date = datetime.now().date()

def main():
    """Main scheduler loop"""
    logger.info("=" * 80)
    logger.info("SALARY RECONCILIATION AGENT SCHEDULER STARTED")
    logger.info("=" * 80)
    logger.info("Monitoring for 16th (EPF Reminder) and 18th (Reconciliation)")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 80)
    
    # Schedule to check every hour
    schedule.every().hour.do(check_and_run_jobs)
    
    # Also check immediately on startup
    check_and_run_jobs()
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nScheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {str(e)}")
