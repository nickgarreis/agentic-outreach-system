# src/agent/tools/message_scheduler.py
# Smart message scheduling that respects daily limits and timing constraints
# Ensures proper spacing between messages and manages multi-campaign scheduling
# RELEVANT FILES: base_tools.py, database_tools.py, outreach_generator.py

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, time
import pytz

from ..agentops_config import track_tool
from .base_tools import BaseTools, ToolResult

logger = logging.getLogger(__name__)


class MessageScheduler(BaseTools):
    """
    Intelligent message scheduler that handles:
    - Daily sending limits per channel
    - 5-minute gaps between messages in same campaign
    - Business hours scheduling (9 AM - 5 PM)
    - Multi-day overflow when limits are reached
    """
    
    # Business hours configuration
    BUSINESS_START_HOUR = 9  # 9 AM
    BUSINESS_END_HOUR = 17   # 5 PM
    MIN_GAP_MINUTES = 5      # Minimum gap between messages in same campaign
    
    def __init__(self):
        """Initialize the message scheduler"""
        super().__init__()
        self.logger = logger
        # Default timezone - in future, make this configurable per campaign
        self.timezone = pytz.timezone('America/New_York')
    
    @track_tool("schedule_outreach_messages")
    async def schedule_outreach_messages(
        self,
        sequences: Dict[str, List[Dict[str, Any]]],
        campaign_id: str,
        lead_id: str,
        daily_limits: Dict[str, int]
    ) -> ToolResult:
        """
        Schedule all messages from the sequences respecting constraints.
        
        Args:
            sequences: Generated message sequences by channel
            campaign_id: Campaign UUID
            lead_id: Lead UUID  
            daily_limits: Daily sending limits by channel
            
        Returns:
            ToolResult with scheduled message details
        """
        try:
            scheduled_messages = []
            scheduling_log = []
            
            # Get current campaign schedule state
            schedule_state = await self._get_campaign_schedule_state(campaign_id)
            
            # Process each channel's sequence
            for channel, messages in sequences.items():
                channel_limit = daily_limits.get(channel, 0)
                if channel_limit == 0:
                    self.logger.warning(f"No daily limit set for {channel}, skipping")
                    continue
                
                # Schedule messages for this channel
                channel_scheduled = await self._schedule_channel_messages(
                    messages=messages,
                    channel=channel,
                    campaign_id=campaign_id,
                    lead_id=lead_id,
                    daily_limit=channel_limit,
                    schedule_state=schedule_state
                )
                
                scheduled_messages.extend(channel_scheduled)
                scheduling_log.append({
                    "channel": channel,
                    "requested": len(messages),
                    "scheduled": len(channel_scheduled)
                })
            
            self.logger.info(
                f"Scheduled {len(scheduled_messages)} messages for lead {lead_id}: "
                f"{scheduling_log}"
            )
            
            return ToolResult(
                success=True,
                data={
                    "scheduled_messages": scheduled_messages,
                    "total_scheduled": len(scheduled_messages),
                    "scheduling_log": scheduling_log,
                    "lead_id": lead_id,
                    "campaign_id": campaign_id
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to schedule messages: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to schedule messages: {str(e)}"
            )
    
    async def _get_campaign_schedule_state(self, campaign_id: str) -> Dict[str, Any]:
        """
        Get current scheduling state for the campaign.
        
        Args:
            campaign_id: Campaign UUID
            
        Returns:
            Dict with schedule information by date and channel
        """
        try:
            client = await self._get_client()
            
            # Get all scheduled messages for this campaign
            response = await client.table("messages")\
                .select("id, channel, send_at, status")\
                .eq("campaign_id", campaign_id)\
                .eq("status", "scheduled")\
                .gte("send_at", datetime.utcnow().isoformat())\
                .execute()
            
            # Organize by date and channel
            schedule_state = {}
            
            for message in response.data:
                send_at = datetime.fromisoformat(message['send_at'].replace('Z', '+00:00'))
                send_date = send_at.date()
                channel = message['channel']
                
                if send_date not in schedule_state:
                    schedule_state[send_date] = {
                        'email': {'count': 0, 'times': []},
                        'linkedin': {'count': 0, 'times': []}
                    }
                
                if channel in schedule_state[send_date]:
                    schedule_state[send_date][channel]['count'] += 1
                    schedule_state[send_date][channel]['times'].append(send_at)
            
            return schedule_state
            
        except Exception as e:
            self.logger.error(f"Failed to get campaign schedule state: {e}")
            return {}
    
    async def _schedule_channel_messages(
        self,
        messages: List[Dict[str, Any]],
        channel: str,
        campaign_id: str,
        lead_id: str,
        daily_limit: int,
        schedule_state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Schedule messages for a specific channel.
        
        Args:
            messages: List of messages to schedule
            channel: Channel type (email/linkedin)
            campaign_id: Campaign UUID
            lead_id: Lead UUID
            daily_limit: Daily sending limit for this channel
            schedule_state: Current campaign schedule
            
        Returns:
            List of scheduled message records
        """
        scheduled = []
        
        for message in messages:
            # Calculate target date based on day_delay
            day_delay = message.get('day_delay', 0)
            target_date = (datetime.utcnow() + timedelta(days=day_delay)).date()
            
            # Find available slot
            send_time = await self._find_available_slot(
                target_date=target_date,
                channel=channel,
                campaign_id=campaign_id,
                daily_limit=daily_limit,
                schedule_state=schedule_state
            )
            
            if not send_time:
                self.logger.warning(
                    f"Could not find available slot for {channel} message "
                    f"(sequence {message.get('sequence_number')})"
                )
                continue
            
            # Create message record
            message_data = {
                "campaign_id": campaign_id,
                "lead_id": lead_id,
                "channel": channel,
                "direction": "outbound",
                "status": "scheduled",
                "send_at": send_time.isoformat(),
                "content": message.get('content', ''),
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Add channel-specific fields
            if channel == "email":
                message_data["subject"] = message.get('subject', '')
            elif channel == "linkedin":
                message_data["message_type"] = message.get('type', 'message')
            
            # Store sequence information in metadata
            message_data["metadata"] = {
                "sequence_number": message.get('sequence_number'),
                "day_delay": day_delay,
                "scheduled_by": "OutreachAgent"
            }
            
            scheduled.append(message_data)
            
            # Update schedule state
            self._update_schedule_state(schedule_state, send_time, channel)
        
        return scheduled
    
    async def _find_available_slot(
        self,
        target_date: datetime.date,
        channel: str,
        campaign_id: str,
        daily_limit: int,
        schedule_state: Dict[str, Any],
        max_days_ahead: int = 14
    ) -> Optional[datetime]:
        """
        Find next available time slot for a message.
        
        Args:
            target_date: Preferred date for sending
            channel: Channel type
            campaign_id: Campaign UUID
            daily_limit: Daily limit for channel
            schedule_state: Current schedule
            max_days_ahead: Maximum days to look ahead
            
        Returns:
            DateTime for sending or None if no slot found
        """
        current_date = target_date
        days_checked = 0
        
        while days_checked < max_days_ahead:
            # Check if we have capacity on this date
            date_schedule = schedule_state.get(current_date, {
                'email': {'count': 0, 'times': []},
                'linkedin': {'count': 0, 'times': []}
            })
            
            channel_schedule = date_schedule.get(channel, {'count': 0, 'times': []})
            
            if channel_schedule['count'] < daily_limit:
                # Find available time slot
                slot_time = self._calculate_next_slot_time(
                    current_date,
                    channel_schedule['times'],
                    campaign_id
                )
                
                if slot_time:
                    return slot_time
            
            # Move to next day
            current_date = current_date + timedelta(days=1)
            days_checked += 1
        
        return None
    
    def _calculate_next_slot_time(
        self,
        target_date: datetime.date,
        existing_times: List[datetime],
        campaign_id: str
    ) -> Optional[datetime]:
        """
        Calculate next available time slot on a specific date.
        
        Args:
            target_date: Date to schedule on
            existing_times: Already scheduled times for this campaign/channel
            campaign_id: Campaign UUID
            
        Returns:
            Next available datetime or None
        """
        # Convert to timezone-aware datetime
        tz = self.timezone
        
        # Start time (9 AM on target date)
        start_time = tz.localize(datetime.combine(
            target_date,
            time(self.BUSINESS_START_HOUR, 0)
        ))
        
        # End time (5 PM on target date)
        end_time = tz.localize(datetime.combine(
            target_date,
            time(self.BUSINESS_END_HOUR, 0)
        ))
        
        # If date is today, start from current time if after business start
        now = datetime.now(tz)
        if target_date == now.date() and now > start_time:
            start_time = now + timedelta(minutes=1)  # Start 1 minute from now
        
        # Sort existing times for this date
        day_times = [
            t for t in existing_times 
            if t.astimezone(tz).date() == target_date
        ]
        day_times.sort()
        
        # If no existing messages, schedule at start time
        if not day_times:
            if start_time < end_time:
                return start_time.astimezone(pytz.UTC)
            return None
        
        # Check for slot at least MIN_GAP_MINUTES after last message
        last_time = max(day_times)
        next_slot = last_time + timedelta(minutes=self.MIN_GAP_MINUTES)
        
        # Ensure it's within business hours
        if next_slot < end_time:
            # If it's before current time, adjust to current time + 1 minute
            if next_slot.astimezone(tz) < now:
                next_slot = now + timedelta(minutes=1)
            
            if next_slot < end_time:
                return next_slot.astimezone(pytz.UTC)
        
        return None
    
    def _update_schedule_state(
        self,
        schedule_state: Dict[str, Any],
        send_time: datetime,
        channel: str
    ):
        """
        Update schedule state with newly scheduled message.
        
        Args:
            schedule_state: Current schedule to update
            send_time: Scheduled send time
            channel: Channel type
        """
        send_date = send_time.date()
        
        if send_date not in schedule_state:
            schedule_state[send_date] = {
                'email': {'count': 0, 'times': []},
                'linkedin': {'count': 0, 'times': []}
            }
        
        if channel in schedule_state[send_date]:
            schedule_state[send_date][channel]['count'] += 1
            schedule_state[send_date][channel]['times'].append(send_time)
    
    @track_tool("get_campaign_availability")  
    async def get_campaign_availability(
        self,
        campaign_id: str,
        daily_limits: Dict[str, int],
        days_ahead: int = 7
    ) -> ToolResult:
        """
        Get available slots for the next N days.
        
        Args:
            campaign_id: Campaign UUID
            daily_limits: Daily limits by channel
            days_ahead: Number of days to check
            
        Returns:
            ToolResult with availability by date and channel
        """
        try:
            schedule_state = await self._get_campaign_schedule_state(campaign_id)
            availability = {}
            
            for i in range(days_ahead):
                check_date = (datetime.utcnow() + timedelta(days=i)).date()
                date_schedule = schedule_state.get(check_date, {
                    'email': {'count': 0, 'times': []},
                    'linkedin': {'count': 0, 'times': []}
                })
                
                availability[check_date.isoformat()] = {
                    'email': {
                        'used': date_schedule.get('email', {}).get('count', 0),
                        'limit': daily_limits.get('email', 0),
                        'available': max(0, daily_limits.get('email', 0) - date_schedule.get('email', {}).get('count', 0))
                    },
                    'linkedin': {
                        'used': date_schedule.get('linkedin', {}).get('count', 0),
                        'limit': daily_limits.get('linkedin', 0),
                        'available': max(0, daily_limits.get('linkedin', 0) - date_schedule.get('linkedin', {}).get('count', 0))
                    }
                }
            
            return ToolResult(
                success=True,
                data={
                    "campaign_id": campaign_id,
                    "availability": availability,
                    "days_checked": days_ahead
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get campaign availability: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to get availability: {str(e)}"
            )