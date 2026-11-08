"""Tests for traffic trigger schemas: scope consistency and name normalisation."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.models.traffic_trigger import (
    ThresholdWindow,
    TrafficDirection,
    TrafficScope,
)
from app.schemas.traffic_trigger import (
    TrafficTriggerCreate,
    TrafficTriggerResponse,
    TrafficTriggerUpdate,
)


def _base(**overrides):
    payload = dict(
        name="monthly cap",
        scope=TrafficScope.GLOBAL,
        threshold_bytes=1024,
        window=ThresholdWindow.LAST_30_DAYS,
    )
    payload.update(overrides)
    return payload


class TestScopeValidation:
    def test_should_require_peer_id_for_peer_scope(self):
        with pytest.raises(PydanticValidationError) as exc_info:
            TrafficTriggerCreate(**_base(scope=TrafficScope.PEER))

        assert "peer_id is required" in str(exc_info.value)

    def test_should_reject_peer_id_for_non_peer_scope(self):
        with pytest.raises(PydanticValidationError) as exc_info:
            TrafficTriggerCreate(**_base(peer_id=5))

        assert "peer_id must be null" in str(exc_info.value)

    def test_should_require_server_id_for_server_scope(self):
        with pytest.raises(PydanticValidationError) as exc_info:
            TrafficTriggerCreate(**_base(scope=TrafficScope.SERVER))

        assert "server_id is required" in str(exc_info.value)

    def test_should_reject_server_id_for_non_server_scope(self):
        with pytest.raises(PydanticValidationError) as exc_info:
            TrafficTriggerCreate(**_base(server_id=9))

        assert "server_id must be null" in str(exc_info.value)

    def test_should_reject_explicit_null_peer_id_for_peer_scope(self):
        with pytest.raises(PydanticValidationError) as exc_info:
            TrafficTriggerCreate(**_base(scope=TrafficScope.PEER, peer_id=None))

        assert "peer_id is required" in str(exc_info.value)

    def test_should_reject_explicit_null_server_id_for_server_scope(self):
        with pytest.raises(PydanticValidationError) as exc_info:
            TrafficTriggerCreate(**_base(scope=TrafficScope.SERVER, server_id=None))

        assert "server_id is required" in str(exc_info.value)

    def test_should_accept_peer_scope_with_peer_id(self):
        trigger = TrafficTriggerCreate(**_base(scope=TrafficScope.PEER, peer_id=3))

        assert trigger.peer_id == 3
        assert trigger.server_id is None

    def test_should_accept_server_scope_with_server_id(self):
        trigger = TrafficTriggerCreate(**_base(scope=TrafficScope.SERVER, server_id=4))

        assert trigger.server_id == 4


class TestFieldConstraints:
    def test_should_reject_empty_name(self):
        with pytest.raises(PydanticValidationError):
            TrafficTriggerCreate(**_base(name=""))

    def test_should_reject_name_longer_than_100_chars(self):
        with pytest.raises(PydanticValidationError):
            TrafficTriggerCreate(**_base(name="n" * 101))

    def test_should_reject_non_positive_threshold(self):
        with pytest.raises(PydanticValidationError):
            TrafficTriggerCreate(**_base(threshold_bytes=0))

    def test_should_reject_negative_cooldown_seconds(self):
        with pytest.raises(PydanticValidationError):
            TrafficTriggerCreate(**_base(cooldown_seconds=-1))

    def test_should_reject_negative_cooldown_minutes(self):
        with pytest.raises(PydanticValidationError):
            TrafficTriggerCreate(**_base(cooldown_minutes=-1))

    def test_should_default_direction_to_combined(self):
        assert TrafficTriggerCreate(**_base()).direction == TrafficDirection.COMBINED


class TestNormalisation:
    def test_should_default_integrations_to_empty_list(self):
        trigger = TrafficTriggerCreate(**_base())

        assert trigger.trigger_integrations == []
        assert trigger.integration_ids == []

    def test_should_copy_integration_ids_to_trigger_integrations(self):
        trigger = TrafficTriggerCreate(**_base(integration_ids=[1, 2]))

        assert trigger.trigger_integrations == [1, 2]

    def test_should_copy_trigger_integrations_to_integration_ids(self):
        trigger = TrafficTriggerCreate(**_base(trigger_integrations=[7]))

        assert trigger.integration_ids == [7]

    def test_should_default_cooldown_to_one_hour(self):
        trigger = TrafficTriggerCreate(**_base())

        assert trigger.cooldown_seconds == 3600
        assert trigger.cooldown_minutes == 60

    def test_should_convert_minutes_to_seconds(self):
        trigger = TrafficTriggerCreate(**_base(cooldown_minutes=5))

        assert trigger.cooldown_seconds == 300

    def test_should_convert_seconds_to_minutes(self):
        trigger = TrafficTriggerCreate(**_base(cooldown_seconds=90))

        assert trigger.cooldown_minutes == 1


class TestUpdateSchema:
    def test_should_allow_partial_payload(self):
        update = TrafficTriggerUpdate(name="renamed")

        assert update.name == "renamed"
        assert update.threshold_bytes is None

    def test_should_not_invent_cooldown_defaults_on_partial_update(self):
        update = TrafficTriggerUpdate(enabled=False)

        assert update.cooldown_seconds is None
        assert update.cooldown_minutes is None

    def test_should_mirror_integration_ids(self):
        update = TrafficTriggerUpdate(integration_ids=[4])

        assert update.trigger_integrations == [4]

    def test_should_mirror_trigger_integrations(self):
        update = TrafficTriggerUpdate(trigger_integrations=[5, 6])

        assert update.integration_ids == [5, 6]

    def test_should_convert_cooldown_minutes_on_update(self):
        update = TrafficTriggerUpdate(cooldown_minutes=3)

        assert update.cooldown_seconds == 180

    def test_should_convert_cooldown_seconds_on_update(self):
        update = TrafficTriggerUpdate(cooldown_seconds=600)

        assert update.cooldown_minutes == 10

    def test_should_reject_zero_threshold(self):
        with pytest.raises(PydanticValidationError):
            TrafficTriggerUpdate(threshold_bytes=0)


class TestResponseFromOrm:
    """from_orm must not lazy-load relationships inside async sessions."""

    async def _make_trigger(self, db_session, scope=TrafficScope.PEER):
        from app.models.peer import Peer
        from app.models.server import Server
        from app.models.traffic_trigger import TrafficTrigger

        peer = Peer(
            id=10, server_id=1, name="laptop", public_key="pk", private_key="sk"
        )
        server = Server(
            id=1, name="wg0", public_key="spk", private_key="ssk", listen_port=51820
        )
        db_session.add_all([server, peer])
        await db_session.flush()
        trigger = TrafficTrigger(
            id=1,
            name="cap",
            description=None,
            scope=scope,
            peer_id=peer.id if scope == TrafficScope.PEER else None,
            server_id=server.id if scope == TrafficScope.SERVER else None,
            direction=TrafficDirection.COMBINED,
            threshold_bytes=1024,
            window=ThresholdWindow.LAST_24_HOURS,
            trigger_integrations=[3],
            trigger_event=True,
            enabled=True,
            cooldown_seconds=120,
            total_triggers=0,
        )
        db_session.add(trigger)
        await db_session.commit()
        return trigger

    async def test_should_expose_names_when_relationships_are_eager_loaded(
        self, db_session
    ):
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.traffic_trigger import TrafficTrigger

        await self._make_trigger(db_session)
        loaded = (
            await db_session.execute(
                select(TrafficTrigger)
                .options(selectinload(TrafficTrigger.peer))
                .where(TrafficTrigger.id == 1)
            )
        ).scalar_one()

        response = TrafficTriggerResponse.from_orm(loaded)

        assert response.peer_name == "laptop"
        assert response.server_name is None
        assert response.cooldown_minutes == 2
        assert response.integration_ids == [3]

    async def test_should_blank_ids_that_do_not_match_scope(self, db_session):
        trigger = await self._make_trigger(db_session, scope=TrafficScope.GLOBAL)

        response = TrafficTriggerResponse.from_orm(trigger)

        assert response.peer_id is None
        assert response.server_id is None

    async def test_should_keep_ids_that_match_scope(self, db_session):
        trigger = await self._make_trigger(db_session, scope=TrafficScope.SERVER)

        response = TrafficTriggerResponse.from_orm(trigger)

        assert response.server_id == 1
        assert response.peer_id is None

    async def test_should_not_raise_when_relationships_are_unloaded(self, db_session):
        trigger = await self._make_trigger(db_session)
        db_session.expire(trigger, ["peer", "server"])

        response = TrafficTriggerResponse.from_orm(trigger)

        # A lazy load here would raise MissingGreenlet inside the async session,
        # so unloaded relationships must simply yield no name.
        assert response.peer_name is None
        assert response.server_name is None
