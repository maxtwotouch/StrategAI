"""Unit tests for leader registry (src/leader/registry.py)."""

import pytest
from src.leader.registry import LeaderRegistry, generate_leader_id


class TestGenerateLeaderId:
    """Tests for generate_leader_id."""

    def test_generates_leader_id(self):
        leader_id = generate_leader_id("Cleopatra VII")
        assert leader_id.startswith("leader_cleopatra_vii_")
        assert len(leader_id) > len("leader_cleopatra_vii_")

    def test_slugifies_name(self):
        leader_id = generate_leader_id("Alexander the Great!")
        assert "alexander_the_great" in leader_id


class TestLeaderRegistry:
    """Tests for LeaderRegistry CRUD operations."""

    def test_generate_leader_id_unique(self):
        id1 = generate_leader_id("Cleopatra VII")
        id2 = generate_leader_id("Cleopatra VII")
        # UUID suffix makes them different
        assert id1 != id2
        assert id1.startswith("leader_cleopatra_vii_")
        assert id2.startswith("leader_cleopatra_vii_")