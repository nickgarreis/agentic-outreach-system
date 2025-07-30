# src/agent/tools/database_tools.py
# Database tools for interacting with Supabase tables
# Provides methods for CRUD operations on campaigns, leads, and messages
# RELEVANT FILES: base_tools.py, ../autopilot_agent.py, ../../database.py

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..agentops_config import track_tool
from .base_tools import BaseTools

logger = logging.getLogger(__name__)


class DatabaseTools(BaseTools):
    """
    Collection of database tools for interacting with Supabase tables.
    Each tool method is decorated with @track_tool for AgentOps monitoring.
    Inherits common functionality from BaseTools.
    """

    # Campaign Tools

    @track_tool("get_campaign")
    async def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve campaign details by ID.

        Args:
            campaign_id: Campaign UUID

        Returns:
            dict: Campaign data or None if not found
        """
        try:
            client = await self._get_client()
            response = (
                await client.table("campaigns")
                .select("*")
                .eq("id", campaign_id)
                .single()
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Failed to get campaign {campaign_id}: {e}")
            return None

    @track_tool("update_campaign_status")
    async def update_campaign_status(self, campaign_id: str, status: str) -> bool:
        """
        Update campaign status.

        Args:
            campaign_id: Campaign UUID
            status: New status (draft, active, paused, completed)

        Returns:
            bool: True if successful
        """
        try:
            client = await self._get_client()
            await client.table("campaigns").update(
                {"status": status, "updated_at": datetime.utcnow().isoformat()}
            ).eq("id", campaign_id).execute()
            logger.info(f"Updated campaign {campaign_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to update campaign status: {e}")
            return False

    @track_tool("get_campaign_leads")
    async def get_campaign_leads(
        self, campaign_id: str, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all leads for a campaign.

        Args:
            campaign_id: Campaign UUID
            status: Optional filter by lead status

        Returns:
            list: List of lead records
        """
        try:
            client = await self._get_client()
            query = client.table("leads").select("*").eq("campaign_id", campaign_id)

            if status:
                query = query.eq("status", status)

            response = await query.execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get campaign leads: {e}")
            return []

    # Lead Tools

    @track_tool("get_lead")
    async def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve lead details by ID.

        Args:
            lead_id: Lead UUID

        Returns:
            dict: Lead data or None if not found
        """
        try:
            client = await self._get_client()
            response = (
                await client.table("leads")
                .select("*")
                .eq("id", lead_id)
                .single()
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Failed to get lead {lead_id}: {e}")
            return None

    @track_tool("update_lead")
    async def update_lead(self, lead_id: str, data: Dict[str, Any]) -> bool:
        """
        Update lead information.

        Args:
            lead_id: Lead UUID
            data: Fields to update

        Returns:
            bool: True if successful
        """
        try:
            client = await self._get_client()
            # Add updated_at timestamp
            data["updated_at"] = datetime.utcnow().isoformat()

            await client.table("leads").update(data).eq("id", lead_id).execute()
            logger.info(f"Updated lead {lead_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update lead: {e}")
            return False

    @track_tool("create_lead")
    async def create_lead(self, lead_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a new lead.

        Args:
            lead_data: Lead information

        Returns:
            dict: Created lead or None if failed
        """
        try:
            client = await self._get_client()
            # Add timestamps
            lead_data["created_at"] = datetime.utcnow().isoformat()
            lead_data["updated_at"] = datetime.utcnow().isoformat()

            response = await client.table("leads").insert(lead_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create lead: {e}")
            return None

    @track_tool("search_leads")
    async def search_leads(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search leads with multiple filters.

        Args:
            filters: Dictionary of field:value pairs to filter by

        Returns:
            list: Matching leads
        """
        try:
            client = await self._get_client()
            query = client.table("leads").select("*")

            # Apply filters
            for field, value in filters.items():
                if value is not None:
                    query = query.eq(field, value)

            response = await query.execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to search leads: {e}")
            return []

    # Message Tools

    @track_tool("create_message")
    async def create_message(
        self, message_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new message.

        Args:
            message_data: Message information including campaign_id, lead_id, content

        Returns:
            dict: Created message or None if failed
        """
        try:
            client = await self._get_client()
            # Add timestamps
            message_data["created_at"] = datetime.utcnow().isoformat()
            message_data["updated_at"] = datetime.utcnow().isoformat()

            response = await client.table("messages").insert(message_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create message: {e}")
            return None

    @track_tool("get_message")
    async def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve message details by ID.

        Args:
            message_id: Message UUID

        Returns:
            dict: Message data or None if not found
        """
        try:
            client = await self._get_client()
            response = (
                await client.table("messages")
                .select("*")
                .eq("id", message_id)
                .single()
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            return None

    @track_tool("update_message_status")
    async def update_message_status(self, message_id: str, status: str) -> bool:
        """
        Update message status.

        Args:
            message_id: Message UUID
            status: New status (draft, scheduled, sent, delivered, opened, replied)

        Returns:
            bool: True if successful
        """
        try:
            client = await self._get_client()
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat(),
            }

            # Add status-specific timestamps
            if status == "sent":
                update_data["sent_at"] = datetime.utcnow().isoformat()
            elif status == "delivered":
                update_data["delivered_at"] = datetime.utcnow().isoformat()
            elif status == "opened":
                update_data["opened_at"] = datetime.utcnow().isoformat()
            elif status == "replied":
                update_data["replied_at"] = datetime.utcnow().isoformat()

            await client.table("messages").update(update_data).eq(
                "id", message_id
            ).execute()
            logger.info(f"Updated message {message_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to update message status: {e}")
            return False

    @track_tool("get_lead_messages")
    async def get_lead_messages(self, lead_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages for a specific lead.

        Args:
            lead_id: Lead UUID

        Returns:
            list: List of messages ordered by creation date
        """
        try:
            client = await self._get_client()
            response = (
                await client.table("messages")
                .select("*")
                .eq("lead_id", lead_id)
                .order("created_at")
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get lead messages: {e}")
            return []

    @track_tool("get_campaign_messages")
    async def get_campaign_messages(
        self, campaign_id: str, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all messages for a campaign.

        Args:
            campaign_id: Campaign UUID
            status: Optional filter by message status

        Returns:
            list: List of messages
        """
        try:
            client = await self._get_client()
            query = client.table("messages").select("*").eq("campaign_id", campaign_id)

            if status:
                query = query.eq("status", status)

            response = await query.order("created_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get campaign messages: {e}")
            return []

    # Analytics Tools

    @track_tool("get_campaign_metrics")
    async def get_campaign_metrics(self, campaign_id: str) -> Dict[str, Any]:
        """
        Calculate campaign metrics and statistics.

        Args:
            campaign_id: Campaign UUID

        Returns:
            dict: Campaign metrics including sent, delivered, opened, replied counts
        """
        try:
            messages = await self.get_campaign_messages(campaign_id)

            metrics = {
                "total_messages": len(messages),
                "draft": sum(1 for m in messages if m.get("status") == "draft"),
                "scheduled": sum(1 for m in messages if m.get("status") == "scheduled"),
                "sent": sum(1 for m in messages if m.get("status") == "sent"),
                "delivered": sum(1 for m in messages if m.get("status") == "delivered"),
                "opened": sum(1 for m in messages if m.get("status") == "opened"),
                "replied": sum(1 for m in messages if m.get("status") == "replied"),
            }

            # Calculate rates
            if metrics["sent"] > 0:
                metrics["delivery_rate"] = (
                    metrics["delivered"] / metrics["sent"]
                ) * 100
                metrics["open_rate"] = (metrics["opened"] / metrics["sent"]) * 100
                metrics["reply_rate"] = (metrics["replied"] / metrics["sent"]) * 100
            else:
                metrics["delivery_rate"] = 0
                metrics["open_rate"] = 0
                metrics["reply_rate"] = 0

            return metrics
        except Exception as e:
            logger.error(f"Failed to calculate campaign metrics: {e}")
            return {}

    @track_tool("get_lead_engagement")
    async def get_lead_engagement(self, lead_id: str) -> Dict[str, Any]:
        """
        Get engagement history for a lead.

        Args:
            lead_id: Lead UUID

        Returns:
            dict: Engagement metrics and timeline
        """
        try:
            messages = await self.get_lead_messages(lead_id)

            engagement = {
                "total_messages": len(messages),
                "first_contact": messages[0]["created_at"] if messages else None,
                "last_contact": messages[-1]["created_at"] if messages else None,
                "messages_sent": sum(
                    1
                    for m in messages
                    if m.get("status") in ["sent", "delivered", "opened", "replied"]
                ),
                "messages_opened": sum(
                    1 for m in messages if m.get("status") in ["opened", "replied"]
                ),
                "messages_replied": sum(
                    1 for m in messages if m.get("status") == "replied"
                ),
                "timeline": [
                    {
                        "message_id": m["id"],
                        "status": m["status"],
                        "created_at": m["created_at"],
                        "sent_at": m.get("sent_at"),
                        "opened_at": m.get("opened_at"),
                        "replied_at": m.get("replied_at"),
                    }
                    for m in messages
                ],
            }

            return engagement
        except Exception as e:
            logger.error(f"Failed to get lead engagement: {e}")
            return {}

    # Bulk Operations

    @track_tool("bulk_update_leads")
    async def bulk_update_leads(
        self, lead_ids: List[str], update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update multiple leads at once.

        Args:
            lead_ids: List of lead UUIDs
            update_data: Fields to update

        Returns:
            dict: Results with success/failure counts
        """
        results = {"successful": 0, "failed": 0, "errors": []}

        for lead_id in lead_ids:
            try:
                success = await self.update_lead(lead_id, update_data.copy())
                if success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(
                        {"lead_id": lead_id, "error": "Update failed"}
                    )
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"lead_id": lead_id, "error": str(e)})

        return results

    @track_tool("bulk_create_messages")
    async def bulk_create_messages(
        self, messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create multiple messages at once.

        Args:
            messages: List of message data dictionaries

        Returns:
            dict: Results with created message IDs and any errors
        """
        results = {"created": [], "failed": [], "errors": []}

        for message_data in messages:
            try:
                created = await self.create_message(message_data)
                if created:
                    results["created"].append(created["id"])
                else:
                    results["failed"].append(message_data)
                    results["errors"].append(
                        {"data": message_data, "error": "Creation failed"}
                    )
            except Exception as e:
                results["failed"].append(message_data)
                results["errors"].append({"data": message_data, "error": str(e)})

        return results
