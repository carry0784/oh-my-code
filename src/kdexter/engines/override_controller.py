"""
Override Controller -- L27 K-Dexter AOS

Purpose: manage human override request lifecycle for B1-tier authorisations.
Only approved L27 human override requests may release LOCKDOWN via
SecurityStateContext.de_escalate("HUMAN_OVERRIDE") and
B1Constitution.release_lockdown(authorized_by="L27_HUMAN").

Governance: B1 (governance_layer_map.md -- L27)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ------------------------------------------------------------------ #
# Enumerations
# ------------------------------------------------------------------ #

class OverrideType(str, Enum):
    LOCKDOWN_RELEASE = "LOCKDOWN_RELEASE"
    CEILING_OVERRIDE = "CEILING_OVERRIDE"
    FORCE_STOP       = "FORCE_STOP"


class OverrideStatus(str, Enum):
    PENDING  = "PENDING"
    APPROVED = "APPROVED"
    DENIED   = "DENIED"
    EXPIRED  = "EXPIRED"


# ------------------------------------------------------------------ #
# Data model
# ------------------------------------------------------------------ #

@dataclass
class OverrideRequest:
    """A single human override request and its current lifecycle state."""
    request_id:    str
    requester:     str
    override_type: OverrideType
    reason:        str
    status:        OverrideStatus = OverrideStatus.PENDING
    created_at:    datetime = field(default_factory=datetime.utcnow)

    # Set when the request is resolved
    resolved_by:     Optional[str] = field(default=None, repr=False)
    resolved_at:     Optional[datetime] = field(default=None, repr=False)
    denial_reason:   Optional[str] = field(default=None, repr=False)


# ------------------------------------------------------------------ #
# L27 Override Controller
# ------------------------------------------------------------------ #

class OverrideController:
    """
    L27 Override Controller.

    Manages the full lifecycle of human override requests:
    submit -> approve | deny | expire.

    Only APPROVED LOCKDOWN_RELEASE requests satisfy the
    B1Constitution.release_lockdown(authorized_by="L27_HUMAN") precondition.

    Usage:
        oc = OverrideController()
        req = oc.submit_request("ops-team", OverrideType.LOCKDOWN_RELEASE, "incident resolved")
        oc.approve(req.request_id, approver="admin")
        if oc.has_approved(OverrideType.LOCKDOWN_RELEASE):
            constitution.release_lockdown(authorized_by="L27_HUMAN")
    """

    def __init__(self) -> None:
        self._requests: dict[str, OverrideRequest] = {}

    # ------------------------------------------------------------------ #
    # Mutating operations
    # ------------------------------------------------------------------ #

    def submit_request(
        self,
        requester: str,
        override_type: OverrideType,
        reason: str,
    ) -> OverrideRequest:
        """
        Submit a new override request.

        Returns:
            OverrideRequest with status PENDING and a fresh request_id.
        """
        request_id = str(uuid.uuid4())
        req = OverrideRequest(
            request_id=request_id,
            requester=requester,
            override_type=override_type,
            reason=reason,
        )
        self._requests[request_id] = req
        return req

    def approve(self, request_id: str, approver: str) -> OverrideRequest:
        """
        Approve a PENDING override request.

        Raises:
            KeyError:   if request_id is not found.
            ValueError: if request is not in PENDING status.
        """
        req = self._get_or_raise(request_id)
        if req.status is not OverrideStatus.PENDING:
            raise ValueError(
                f"Cannot approve request {request_id}: status is {req.status.value}"
            )
        req.status      = OverrideStatus.APPROVED
        req.resolved_by = approver
        req.resolved_at = datetime.utcnow()
        return req

    def deny(self, request_id: str, approver: str, reason: str) -> OverrideRequest:
        """
        Deny a PENDING override request.

        Raises:
            KeyError:   if request_id is not found.
            ValueError: if request is not in PENDING status.
        """
        req = self._get_or_raise(request_id)
        if req.status is not OverrideStatus.PENDING:
            raise ValueError(
                f"Cannot deny request {request_id}: status is {req.status.value}"
            )
        req.status        = OverrideStatus.DENIED
        req.resolved_by   = approver
        req.resolved_at   = datetime.utcnow()
        req.denial_reason = reason
        return req

    def expire(self, request_id: str) -> OverrideRequest:
        """
        Mark a PENDING request as EXPIRED (e.g. TTL enforcement by a scheduler).

        Raises:
            KeyError:   if request_id is not found.
            ValueError: if request is not in PENDING status.
        """
        req = self._get_or_raise(request_id)
        if req.status is not OverrideStatus.PENDING:
            raise ValueError(
                f"Cannot expire request {request_id}: status is {req.status.value}"
            )
        req.status      = OverrideStatus.EXPIRED
        req.resolved_at = datetime.utcnow()
        return req

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_pending(self) -> list[OverrideRequest]:
        """Return all requests currently in PENDING status."""
        return [r for r in self._requests.values() if r.status is OverrideStatus.PENDING]

    def has_approved(self, override_type: OverrideType) -> bool:
        """
        Return True if at least one APPROVED request of override_type exists.

        Used by B1Constitution to verify L27 authorisation before
        calling release_lockdown(authorized_by="L27_HUMAN").
        """
        return any(
            r.status is OverrideStatus.APPROVED and r.override_type is override_type
            for r in self._requests.values()
        )

    def get(self, request_id: str) -> Optional[OverrideRequest]:
        """Return the request for request_id, or None if not found."""
        return self._requests.get(request_id)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _get_or_raise(self, request_id: str) -> OverrideRequest:
        req = self._requests.get(request_id)
        if req is None:
            raise KeyError(f"Override request not found: {request_id}")
        return req
