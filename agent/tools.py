import copy

# ── Seed data ────────────────────────────────────────────────────────────────

_SLOT_SEED = {
    "2026-09-24": [
        {"id": "S001", "time": "09:00", "provider": "Dr. Smith", "specialty": "General"},
        {"id": "S002", "time": "10:30", "provider": "Dr. Smith", "specialty": "General"},
        {"id": "S003", "time": "14:00", "provider": "Dr. Jones", "specialty": "Cardiology"},
    ],
    "2026-09-25": [
        {"id": "S004", "time": "09:00", "provider": "Dr. Smith", "specialty": "General"},
        {"id": "S005", "time": "11:00", "provider": "Dr. Brown", "specialty": "Dermatology"},
        {"id": "S006", "time": "15:00", "provider": "Dr. Jones", "specialty": "Cardiology"},
    ],
    "2026-09-26": [
        {"id": "S007", "time": "09:30", "provider": "Dr. Smith", "specialty": "General"},
        {"id": "S008", "time": "13:00", "provider": "Dr. Brown", "specialty": "Dermatology"},
    ],
    "2026-09-28": [
        {"id": "S009", "time": "10:00", "provider": "Dr. Smith", "specialty": "General"},
        {"id": "S010", "time": "11:30", "provider": "Dr. Jones", "specialty": "Cardiology"},
        {"id": "S011", "time": "14:30", "provider": "Dr. Brown", "specialty": "Dermatology"},
    ],
    "2026-09-29": [
        {"id": "S012", "time": "09:00", "provider": "Dr. Jones", "specialty": "Cardiology"},
        {"id": "S013", "time": "10:30", "provider": "Dr. Smith", "specialty": "General"},
        {"id": "S014", "time": "15:00", "provider": "Dr. Brown", "specialty": "Dermatology"},
    ],
    "2026-09-30": [
        {"id": "S015", "time": "09:30", "provider": "Dr. Smith", "specialty": "General"},
        {"id": "S016", "time": "11:00", "provider": "Dr. Jones", "specialty": "Cardiology"},
        {"id": "S017", "time": "14:00", "provider": "Dr. Brown", "specialty": "Dermatology"},
    ],
}

_APT_SEED = {
    "A001": {
        "patient_name": "John Doe", "patient_phone": "555-1234",
        "date": "2026-09-24",      "time": "09:00",
        "provider": "Dr. Smith",   "reason": "Follow-up",
        "slot_id": "S001",
    }
}

_db: dict = {"slots": {}, "appointments": {}, "next_id": 2}


def reset_db() -> None:
    _db["slots"]        = copy.deepcopy(_SLOT_SEED)
    _db["appointments"] = copy.deepcopy(_APT_SEED)
    _db["next_id"]      = 2


reset_db()


# ── Tool implementations ──────────────────────────────────────────────────────

def check_availability(date: str, time_preference: str = "any", specialty: str | None = None) -> dict:
    slots = list(_db["slots"].get(date, []))
    if specialty:
        slots = [s for s in slots if s["specialty"].lower() == specialty.lower()]
    if time_preference == "morning":
        slots = [s for s in slots if s["time"] < "12:00"]
    elif time_preference == "afternoon":
        slots = [s for s in slots if "12:00" <= s["time"] < "17:00"]
    elif time_preference == "evening":
        slots = [s for s in slots if s["time"] >= "17:00"]
    return {"available_slots": slots, "date": date, "count": len(slots)}


def _find_slot_date(slot_id: str) -> str | None:
    return next(
        (d for d, slots in _db["slots"].items() if any(s["id"] == slot_id for s in slots)),
        None,
    )


def book_appointment(patient_name: str, patient_phone: str, slot_id: str, reason: str) -> dict:
    slot_date = _find_slot_date(slot_id)
    slot      = next((s for s in _db["slots"].get(slot_date or "", []) if s["id"] == slot_id), None)
    if not slot:
        return {"success": False, "error": f"Slot {slot_id} not found or already booked"}
    apt_id = f"A{_db['next_id']:03d}"
    _db["next_id"] += 1
    _db["appointments"][apt_id] = {
        "patient_name": patient_name, "patient_phone": patient_phone,
        "date": slot_date, "time": slot["time"],
        "provider": slot["provider"], "reason": reason, "slot_id": slot_id,
    }
    _db["slots"][slot_date] = [s for s in _db["slots"][slot_date] if s["id"] != slot_id]
    return {"success": True, "appointment_id": apt_id, "date": slot_date,
            "time": slot["time"], "provider": slot["provider"]}


def cancel_appointment(appointment_id: str, reason: str = "") -> dict:
    apt = _db["appointments"].pop(appointment_id, None)
    if not apt:
        return {"success": False, "error": f"Appointment {appointment_id} not found"}
    restored = {"id": apt["slot_id"], "time": apt["time"], "provider": apt["provider"], "specialty": "General"}
    _db["slots"].setdefault(apt["date"], []).append(restored)
    return {"success": True, "appointment_id": appointment_id, "cancelled_details": apt}


def get_appointment(patient_name: str | None = None, appointment_id: str | None = None) -> dict:
    if appointment_id:
        apt = _db["appointments"].get(appointment_id)
        return {"found": bool(apt), "appointments": [apt] if apt else []}
    if patient_name:
        matches = [{"id": aid, **apt} for aid, apt in _db["appointments"].items()
                   if patient_name.lower() in apt["patient_name"].lower()]
        return {"found": bool(matches), "appointments": matches}
    return {"found": False, "appointments": []}


# ── Tool dispatch ─────────────────────────────────────────────────────────────

TOOL_MAP = {
    "check_availability":  check_availability,
    "book_appointment":    book_appointment,
    "cancel_appointment":  cancel_appointment,
    "get_appointment":     get_appointment,
}


def dispatch_tool(name: str, inputs: dict) -> dict:
    fn = TOOL_MAP.get(name)
    return fn(**inputs) if fn else {"error": f"Unknown tool: {name}"}


# ── Tool definitions (sent to Claude) ────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "check_availability",
        "description": "Check open appointment slots for a given date. Always call this before booking.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date":            {"type": "string", "description": "Date in YYYY-MM-DD"},
                "time_preference": {"type": "string", "enum": ["morning", "afternoon", "evening", "any"]},
                "specialty":       {"type": "string", "description": "Optional: General, Cardiology, Dermatology"},
            },
            "required": ["date"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Book an appointment using a slot_id from check_availability. Requires patient confirmation first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_name":  {"type": "string"},
                "patient_phone": {"type": "string"},
                "slot_id":       {"type": "string", "description": "Slot ID from check_availability"},
                "reason":        {"type": "string"},
            },
            "required": ["patient_name", "patient_phone", "slot_id", "reason"],
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an existing appointment by its ID. Requires patient confirmation first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string"},
                "reason":         {"type": "string"},
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "get_appointment",
        "description": "Look up existing appointments by patient name or appointment ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_name":   {"type": "string"},
                "appointment_id": {"type": "string"},
            },
        },
    },
]
