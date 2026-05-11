import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()


def _whatsapp_base_url() -> str:
    raw = (os.getenv("WHATSAPP_API_URL") or "").strip().rstrip("/")
    if not raw:
        raise ValueError("WHATSAPP_API_URL environment variable is required")
    if not raw.startswith(("http://", "https://")):
        return f"http://{raw}"
    return raw


def _api_error_message(response: httpx.Response) -> str:
    try:
        body: dict[str, Any] = response.json()
        err = body.get("error", "Request failed")
        details = body.get("details")
        if details:
            return f"Error: {err} — {details}"
        return f"Error: {err}"
    except Exception:
        return f"Error: HTTP {response.status_code} — {response.text}"


@tool
def create_whatsapp_poll(title: str, group_id: str, options_json: str) -> str:
    """
    Create a WhatsApp group poll. Votes are stored server-side; use get_whatsapp_poll_status to read results.

    Args:
        title: Poll title (the question shown in WhatsApp).
        group_id: The group id of the chat you are in.
        options_json: JSON array of choice strings, e.g. '["Yes","No","Maybe"]'. At least one option is required.

    Returns:
        Success message including poll_id, or an error message.
    """
    try:
        try:
            options = json.loads(options_json)
        except json.JSONDecodeError as e:
            return f"Error: options_json must be valid JSON — {e}"

        if not isinstance(options, list):
            return "Error: options_json must be a JSON array of strings"
        if len(options) < 1:
            return "Error: at least one poll option is required"
        if not all(isinstance(o, str) for o in options):
            return "Error: every option must be a string"

        payload = {"title": title, "options": options, "group_id": group_id}
        url = f"{_whatsapp_base_url()}/poll/create"

        with httpx.Client() as client:
            response = client.post(url, json=payload, timeout=30.0)

        if response.status_code != 200:
            return _api_error_message(response)

        data = response.json()
        if data.get("status") == "success" and data.get("poll_id") is not None:
            return f"Poll created successfully. poll_id: {data['poll_id']}"
        return f"Error: unexpected response — {data!r}"
    except httpx.HTTPError as e:
        return f"Error: HTTP request failed — {e}"
    except Exception as e:
        return f"Error: {e}"


@tool
def get_whatsapp_poll_status(poll_id: str) -> str:
    """
    Fetch current vote counts for a poll. Only options with at least one vote appear in the result;
    options with zero votes are omitted from the API. The result will contain user_ids of the users who voted for the option.

    Args:
        poll_id: The poll id returned by create_whatsapp_poll.

    Returns:
        Human-readable summary of votes per option, or an error message.
    """
    try:
        url = f"{_whatsapp_base_url()}/poll/status"
        with httpx.Client() as client:
            response = client.get(url, params={"poll_id": poll_id}, timeout=30.0)

        if response.status_code != 200:
            return _api_error_message(response)

        data = response.json()
        if data.get("status") != "success":
            return f"Error: unexpected response — {data!r}"

        options = data.get("options")
        if not isinstance(options, list):
            return f"Error: unexpected options field — {options!r}"

        if not options:
            return "Poll status: no votes yet (only options with votes are returned by the API)."

        lines = ["Poll status (options with at least one vote):"]
        for item in options:
            if not isinstance(item, dict):
                lines.append(f"- {item!r}")
                continue
            label = item.get("option", "?")
            users = item.get("users", [])
            if isinstance(users, list) and users:
                lines.append(f"- {label}: {', '.join(str(u) for u in users)}")
            else:
                lines.append(f"- {label}: (no users listed)")

        lines.append(
            "Note: options with zero votes are not included in this list."
        )
        return "\n".join(lines)
    except httpx.HTTPError as e:
        return f"Error: HTTP request failed — {e}"
    except Exception as e:
        return f"Error: {e}"
