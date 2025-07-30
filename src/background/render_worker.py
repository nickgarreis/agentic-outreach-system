# src/background/render_worker.py
# Render background worker for executing AutopilotAgent jobs
# Manages job scheduling, execution, and monitoring with AgentOps integration
# RELEVANT FILES: ../agent/autopilot_agent.py, ../config/agentops_config.py, ../database.py

import asyncio
import logging
import signal
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ..config import get_settings
from ..agent.agentops_config import (
    init_agentops,
    AgentOpsContextManager,
    create_session_tags,
)
from ..database import get_supabase
from ..agent import AutopilotAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RenderWorker:
    """
    Background worker for processing AutopilotAgent jobs.
    Polls for jobs, executes them with AgentOps tracking, and updates status.
    """

    def __init__(self):
        """Initialize the worker with settings and connections"""
        self.settings = get_settings()
        self.supabase = None
        self.running = False
        self.current_job = None

        # Worker configuration
        self.poll_interval = 10  # seconds between job checks
        self.max_retries = 3
        self.job_timeout = 300  # 5 minutes max per job

        logger.info("Initialized RenderWorker")

    async def start(self):
        """Start the worker and begin processing jobs"""
        logger.info("Starting RenderWorker...")

        # Initialize AgentOps
        if init_agentops():
            logger.info("✓ AgentOps initialized for worker")
        else:
            logger.warning("⚠ Running without AgentOps tracking")

        # Initialize Supabase with secret key for backend operations
        self.supabase = await get_supabase(use_secret_key=True)
        logger.info("✓ Connected to Supabase with secret key")

        # Set up graceful shutdown handlers
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

        self.running = True
        logger.info("✓ RenderWorker started, beginning job processing")

        # Start job processing loop
        await self._process_jobs()

    def _shutdown_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

        if self.current_job:
            logger.warning(f"Interrupting current job: {self.current_job['id']}")

    async def _process_jobs(self):
        """Main job processing loop"""
        while self.running:
            try:
                # Check for pending jobs
                job = await self._get_next_job()

                if job:
                    self.current_job = job
                    await self._execute_job(job)
                    self.current_job = None
                else:
                    # No jobs available, wait before checking again
                    await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in job processing loop: {e}")
                await asyncio.sleep(self.poll_interval)

        logger.info("Job processing loop ended")

    async def _get_next_job(self) -> Optional[Dict[str, Any]]:
        """
        Fetch the next pending job from the job queue.

        Returns:
            dict: Job data or None if no jobs available
        """
        try:
            # Query for pending jobs, ordered by priority and created_at
            response = (
                self.supabase.table("jobs")
                .select("*")
                .eq("status", "pending")
                .order("priority", desc=True)
                .order("created_at")
                .limit(1)
                .execute()
            )

            if response.data:
                job = response.data[0]

                # Immediately mark job as processing to prevent double processing
                self.supabase.table("jobs").update(
                    {
                        "status": "processing",
                        "started_at": datetime.utcnow().isoformat(),
                        "worker_id": self.settings.render_service_id or "local",
                    }
                ).eq("id", job["id"]).execute()

                logger.info(f"Picked up job: {job['id']} ({job['job_type']})")
                return job

            return None

        except Exception as e:
            logger.error(f"Error fetching next job: {e}")
            return None

    async def _execute_job(self, job: Dict[str, Any]):
        """
        Execute a job with AgentOps session tracking.

        Args:
            job: Job data from database
        """
        job_id = job["id"]
        job_type = job["job_type"]
        job_data = job.get("data", {})

        logger.info(f"Executing job {job_id} of type {job_type}")

        # Create session tags for AgentOps
        session_tags = create_session_tags(
            job_type=job_type,
            job_id=job_id,
            campaign_id=job_data.get("campaign_id"),
            priority=job.get("priority", "normal"),
        )

        # Execute job within AgentOps session
        async with AgentOpsContextManager(
            session_name=f"{job_type}_{job_id}", tags=session_tags
        ):
            try:
                # Create agent instance for this job
                agent = AutopilotAgent(job_type=job_type, job_id=job_id)

                # Execute job with timeout
                result = await asyncio.wait_for(
                    agent.execute_job(job_data), timeout=self.job_timeout
                )

                # Update job status to completed
                await self._update_job_status(job_id, "completed", result)
                logger.info(f"Job {job_id} completed successfully")

            except asyncio.TimeoutError:
                error_result = {
                    "error": f"Job timed out after {self.job_timeout} seconds",
                    "timeout": True,
                }
                await self._update_job_status(job_id, "failed", error_result)
                logger.error(f"Job {job_id} timed out")

            except Exception as e:
                error_result = {"error": str(e), "error_type": type(e).__name__}

                # Check if we should retry
                retry_count = job.get("retry_count", 0)
                if retry_count < self.max_retries:
                    await self._retry_job(job_id, retry_count + 1)
                    logger.warning(
                        f"Job {job_id} failed, will retry ({retry_count + 1}/{self.max_retries})"
                    )
                else:
                    await self._update_job_status(job_id, "failed", error_result)
                    logger.error(
                        f"Job {job_id} failed after {retry_count} retries: {e}"
                    )

    async def _update_job_status(
        self, job_id: str, status: str, result: Dict[str, Any]
    ):
        """
        Update job status in database.

        Args:
            job_id: Job UUID
            status: New status (completed, failed)
            result: Job execution result
        """
        try:
            update_data = {
                "status": status,
                "result": result,
                "updated_at": datetime.utcnow().isoformat(),
            }

            if status == "completed":
                update_data["completed_at"] = datetime.utcnow().isoformat()
            elif status == "failed":
                update_data["failed_at"] = datetime.utcnow().isoformat()

            self.supabase.table("jobs").update(update_data).eq(
                "id", job_id
            ).execute()

        except Exception as e:
            logger.error(f"Failed to update job status: {e}")

    async def _retry_job(self, job_id: str, retry_count: int):
        """
        Schedule job for retry.

        Args:
            job_id: Job UUID
            retry_count: New retry count
        """
        try:
            # Calculate backoff delay (exponential backoff)
            delay_seconds = min(60 * (2 ** (retry_count - 1)), 3600)  # Max 1 hour
            retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)

            await self.supabase.table("jobs").update(
                {
                    "status": "pending",
                    "retry_count": retry_count,
                    "retry_at": retry_at.isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
            ).eq("id", job_id).execute()

        except Exception as e:
            logger.error(f"Failed to schedule job retry: {e}")

    async def stop(self):
        """Stop the worker gracefully"""
        logger.info("Stopping RenderWorker...")
        self.running = False

        # Wait for current job to complete if any
        if self.current_job:
            logger.info("Waiting for current job to complete...")
            # Give it max 30 seconds to complete
            await asyncio.sleep(30)

        logger.info("RenderWorker stopped")


class JobScheduler:
    """
    Utility class for scheduling jobs to be processed by the worker.
    Used by other parts of the application to queue jobs.
    """

    @staticmethod
    async def schedule_job(
        job_type: str,
        data: Dict[str, Any],
        priority: str = "normal",
        scheduled_for: Optional[datetime] = None,
    ) -> Optional[str]:
        """
        Schedule a new job for processing.

        Args:
            job_type: Type of job (campaign_execution, lead_enrichment, etc.)
            data: Job-specific data
            priority: Job priority (low, normal, high)
            scheduled_for: Optional future execution time

        Returns:
            str: Job ID if created successfully
        """
        try:
            supabase = await get_supabase()

            job_data = {
                "job_type": job_type,
                "data": data,
                "priority": priority,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            if scheduled_for:
                job_data["scheduled_for"] = scheduled_for.isoformat()

            response = await supabase.table("jobs").insert(job_data).execute()

            if response.data:
                job_id = response.data[0]["id"]
                logger.info(f"Scheduled job {job_id} of type {job_type}")
                return job_id

            return None

        except Exception as e:
            logger.error(f"Failed to schedule job: {e}")
            return None

    @staticmethod
    async def cancel_job(job_id: str) -> bool:
        """
        Cancel a pending job.

        Args:
            job_id: Job UUID

        Returns:
            bool: True if cancelled successfully
        """
        try:
            supabase = await get_supabase()

            # Only cancel if job is still pending
            supabase.table("jobs").update(
                {
                    "status": "cancelled",
                    "cancelled_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
            ).eq("id", job_id).eq("status", "pending").execute()

            logger.info(f"Cancelled job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel job: {e}")
            return False

    @staticmethod
    async def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a job.

        Args:
            job_id: Job UUID

        Returns:
            dict: Job status information
        """
        try:
            supabase = await get_supabase()
            response = (
                supabase.table("jobs")
                .select("*")
                .eq("id", job_id)
                .single()
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return None


# Main entry point for running the worker
async def main():
    """Main function to run the worker"""
    worker = RenderWorker()

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
    finally:
        await worker.stop()


if __name__ == "__main__":
    # Run the worker
    asyncio.run(main())
