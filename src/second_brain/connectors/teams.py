"""Microsoft Teams connector via Microsoft Graph API."""
import logging
from datetime import datetime, timedelta, timezone

from second_brain.config import get_config
from second_brain.connectors.base import BaseConnector
from second_brain.models import Item, ItemMeta

logger = logging.getLogger("second-brain.connectors.teams")


class TeamsConnector(BaseConnector):
    """Connector that ingests messages from Microsoft Teams into the work store."""

    def __init__(self):
        super().__init__(name="Teams", target_store="work")
        self._config = get_config()
        self._client = None
        self._credential = None

    async def authenticate(self) -> bool:
        """Authenticate using MSAL device code flow via msgraph-sdk."""
        try:
            from azure.identity import DeviceCodeCredential
            from msgraph import GraphServiceClient

            self._credential = DeviceCodeCredential(
                client_id=self._config.microsoft.client_id,
                tenant_id=self._config.microsoft.tenant_id,
            )
            self._client = GraphServiceClient(
                credentials=self._credential,
                scopes=["https://graph.microsoft.com/.default"],
            )
            # Test the connection
            me = await self._client.me.get()
            logger.info(f"Authenticated as: {me.display_name}")
            return True
        except Exception as e:
            logger.error(f"Teams authentication failed: {e}")
            return False

    async def fetch_new_items(self, days_back: int = 7) -> list[Item]:
        """Fetch recent Teams messages from joined teams/channels."""
        if not self._client:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        items: list[Item] = []
        since = datetime.now(timezone.utc) - timedelta(days=days_back)

        try:
            # Get joined teams
            teams_response = await self._client.me.joined_teams.get()
            if not teams_response or not teams_response.value:
                logger.info("No joined teams found.")
                return items

            for team in teams_response.value:
                try:
                    # Get channels for each team
                    channels_response = await self._client.teams.by_team_id(
                        team.id
                    ).channels.get()

                    if not channels_response or not channels_response.value:
                        continue

                    for channel in channels_response.value:
                        try:
                            # Get recent messages from each channel
                            messages_response = await self._client.teams.by_team_id(
                                team.id
                            ).channels.by_channel_id(
                                channel.id
                            ).messages.get()

                            if not messages_response or not messages_response.value:
                                continue

                            for msg in messages_response.value:
                                # Filter by date
                                if msg.created_date_time and msg.created_date_time < since:
                                    continue

                                # Skip empty or system messages
                                if not msg.body or not msg.body.content:
                                    continue

                                content = msg.body.content
                                sender = (
                                    msg.from_property.user.display_name
                                    if msg.from_property and msg.from_property.user
                                    else "Unknown"
                                )

                                item = Item(
                                    meta=ItemMeta(
                                        title=f"Teams: {team.display_name}/{channel.display_name} - {sender}",
                                        source="teams",
                                        store="work",
                                        category="Inbox",
                                        tags=["teams", team.display_name.lower().replace(" ", "-")],
                                        created=msg.created_date_time or datetime.now(),
                                        summary=content[:200] if content else "",
                                    ),
                                    content=(
                                        f"**From:** {sender}\n"
                                        f"**Team:** {team.display_name}\n"
                                        f"**Channel:** {channel.display_name}\n"
                                        f"**Date:** {msg.created_date_time}\n\n"
                                        f"{content}"
                                    ),
                                )
                                items.append(item)

                        except Exception as e:
                            logger.warning(
                                f"Failed to fetch messages from {channel.display_name}: {e}"
                            )

                except Exception as e:
                    logger.warning(
                        f"Failed to fetch channels from {team.display_name}: {e}"
                    )

        except Exception as e:
            logger.error(f"Failed to fetch teams: {e}")
            raise

        logger.info(f"Fetched {len(items)} messages from Teams")
        return items

    async def get_status(self) -> dict:
        """Get Teams connector status."""
        authenticated = self._client is not None
        return {
            "connector": "Teams",
            "authenticated": authenticated,
            "target_store": self.target_store,
            "client_id": (
                self._config.microsoft.client_id[:8] + "..."
                if self._config.microsoft.client_id
                else "not configured"
            ),
        }
