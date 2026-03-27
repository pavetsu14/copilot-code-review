"""
Announcement endpoints for the High School Management System API
"""

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from ..database import announcements_collection, teachers_collection, verify_password

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _parse_date(value: Optional[str], field_name: str, required: bool = False) -> Optional[date]:
    if value is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required")
        return None

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must use YYYY-MM-DD format"
        ) from exc


def _validate_teacher(teacher_username: Optional[str], teacher_password: Optional[str]) -> Dict[str, Any]:
    if not teacher_username or not teacher_password:
        raise HTTPException(status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher or not verify_password(teacher.get("password", ""), teacher_password):
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


def _validate_dates(starts_on: Optional[str], expires_on: str) -> Dict[str, Optional[str]]:
    start_date = _parse_date(starts_on, "starts_on", required=False)
    expiration_date = _parse_date(expires_on, "expires_on", required=True)

    if start_date and expiration_date < start_date:
        raise HTTPException(status_code=400, detail="expires_on must be on or after starts_on")

    return {
        "starts_on": start_date.isoformat() if start_date else None,
        "expires_on": expiration_date.isoformat()
    }


@router.get("", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get currently active announcements visible to all visitors."""
    today = date.today().isoformat()

    query = {
        "expires_on": {"$gte": today},
        "$or": [
            {"starts_on": None},
            {"starts_on": {"$exists": False}},
            {"starts_on": {"$lte": today}}
        ]
    }

    announcements: List[Dict[str, Any]] = []
    for item in announcements_collection.find(query).sort([("expires_on", 1), ("starts_on", 1)]):
        announcements.append({
            "id": item["_id"],
            "message": item["message"],
            "starts_on": item.get("starts_on"),
            "expires_on": item["expires_on"]
        })

    return announcements


@router.get("/manage", response_model=List[Dict[str, Any]])
def get_all_announcements(
    teacher_username: Optional[str] = Query(None),
    teacher_password: Optional[str] = Query(None)
) -> List[Dict[str, Any]]:
    """Get all announcements for management dashboard - requires teacher authentication."""
    _validate_teacher(teacher_username, teacher_password)

    announcements: List[Dict[str, Any]] = []
    for item in announcements_collection.find().sort([("expires_on", 1), ("starts_on", 1)]):
        announcements.append({
            "id": item["_id"],
            "message": item["message"],
            "starts_on": item.get("starts_on"),
            "expires_on": item["expires_on"]
        })

    return announcements


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    expires_on: str,
    starts_on: Optional[str] = None,
    teacher_username: Optional[str] = Query(None),
    teacher_password: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Create a new announcement - requires teacher authentication."""
    _validate_teacher(teacher_username, teacher_password)

    if not message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    date_values = _validate_dates(starts_on, expires_on)

    announcement_id = str(uuid4())
    new_announcement = {
        "_id": announcement_id,

        "message": message.strip(),
        "starts_on": date_values["starts_on"],
        "expires_on": date_values["expires_on"]
    }

    announcements_collection.insert_one(new_announcement)

    return {
        "id": announcement_id,
        "message": new_announcement["message"],
        "starts_on": new_announcement["starts_on"],
        "expires_on": new_announcement["expires_on"]
    }


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    expires_on: str,
    starts_on: Optional[str] = None,
    teacher_username: Optional[str] = Query(None),
    teacher_password: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Update an existing announcement - requires teacher authentication."""
    _validate_teacher(teacher_username, teacher_password)

    if not message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    existing = announcements_collection.find_one({"_id": announcement_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")

    date_values = _validate_dates(starts_on, expires_on)

    updates = {
        "message": message.strip(),
        "starts_on": date_values["starts_on"],
        "expires_on": date_values["expires_on"]
    }

    announcements_collection.update_one(
        {"_id": announcement_id},
        {"$set": updates}
    )

    return {
        "id": announcement_id,
        **updates
    }


@router.delete("/{announcement_id}", response_model=Dict[str, str])
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None),
    teacher_password: Optional[str] = Query(None)
) -> Dict[str, str]:
    """Delete an announcement - requires teacher authentication."""
    _validate_teacher(teacher_username, teacher_password)

    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
