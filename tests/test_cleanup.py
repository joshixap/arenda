"""Unit test for cleanup logic (mocked session)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from parser_service.cleanup import run_cleanup
from shared.models import ListingStatus


@pytest.mark.asyncio
async def test_cleanup_deletes_old_inactive():
    old_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [old_id]

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()

    deleted = await run_cleanup(session, publisher=None)
    assert deleted == 1
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_nothing_to_delete():
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()

    deleted = await run_cleanup(session, publisher=None)
    assert deleted == 0
    session.commit.assert_not_called()
