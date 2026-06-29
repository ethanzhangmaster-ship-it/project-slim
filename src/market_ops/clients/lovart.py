"""Lovart OpenClaw API client for AI image generation.

Implements AK/SK HMAC-SHA256 authentication and async polling workflow:
  1. POST /v1/openapi/chat  → submit prompt + model preference
  2. GET  /v1/openapi/chat/result?thread_id=XXX  → poll until done
  3. Download generated image URLs

Only uses two models as configured:
  - generate_image_nano_banana  (Nano Banana)
  - generate_image_gpt_image_2  (GPT Image 2)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests as _requests


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_DEFAULT_BASE_URL = "https://lgw.lovart.ai"
_API_PREFIX = "/v1/openapi"
_USER_AGENT = "MarketOps/1.0"
_POLL_INTERVAL_SEC = 5
_POLL_MAX_WAIT_SEC = 300  # 5 min max per image

# Allowed models (user requirement: only nano banana + gpt-2)
ALLOWED_MODELS = {
    "nano_banana": "generate_image_nano_banana",
    "gpt_image_2": "generate_image_gpt_image_2",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class LovartResult:
    """Result from a Lovart generation request."""
    thread_id: str
    status: str  # done / pending_confirmation / abort / timeout
    image_urls: list[str] = field(default_factory=list)
    assistant_text: str = ""
    project_id: str = ""
    elapsed_sec: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class LovartClient:
    """Lovart OpenClaw API client with HMAC-SHA256 auth."""

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        base_url: str | None = None,
        models: list[str] | None = None,
        mode: str = "fast",
    ) -> None:
        self._ak = (access_key or os.getenv("LOVART_ACCESS_KEY", "")).strip()
        self._sk = (secret_key or os.getenv("LOVART_SECRET_KEY", "")).strip()
        self._base = (base_url or os.getenv("LOVART_BASE_URL", _DEFAULT_BASE_URL)).strip().rstrip("/")
        self._mode = (mode or os.getenv("LOVART_MODE", "fast")).strip()

        # Parse models from env if not provided
        if models is None:
            env_models = os.getenv("LOVART_MODELS", "")
            if env_models:
                models = [m.strip() for m in env_models.strip().split(",") if m.strip()]
        self._models = models or list(ALLOWED_MODELS.values())

        if not self._ak or not self._sk:
            raise ValueError("Lovart AK/SK not configured. Set LOVART_ACCESS_KEY and LOVART_SECRET_KEY.")

        # Lazy-initialized default project
        self._default_project_id: str | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._ak and self._sk)

    # ----- Project management -----

    def ensure_project(self, name: str = "market_ops_creative") -> str:
        """Get or create a default project for image generation.

        Returns the project_id.
        """
        if self._default_project_id:
            return self._default_project_id

        # Try to create/reuse project
        try:
            resp = self._api_post("/project/save", {"name": name})
            data = resp.get("data", resp)
            pid = data.get("project_id") or data.get("id", "")
            if pid:
                self._default_project_id = pid
                return pid
        except Exception as exc:
            print(f"[Lovart] Project create warning: {exc}")

        # Fallback: generate a UUID-based project_id
        self._default_project_id = f"proj_{uuid.uuid4().hex[:12]}"
        return self._default_project_id

    # ----- File upload -----

    def upload_file(self, file_path: str | Path) -> str:
        """Upload a local file to Lovart CDN.

        Returns the CDN URL of the uploaded file.
        """
        path = f"{_API_PREFIX}/file/upload"
        url = f"{self._base}{path}"

        headers = self._sign("POST", path)
        headers["User-Agent"] = _USER_AGENT

        file_path = Path(file_path)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        with open(file_path, "rb") as f:
            resp = _requests.post(
                url,
                headers=headers,
                files={"file": (file_path.name, f)},
                timeout=120,
                verify=False,
            )
        resp.raise_for_status()
        data = resp.json().get("data", resp.json())
        cdn_url = data.get("url", "")
        if not cdn_url:
            raise RuntimeError(f"Upload failed: no URL in response: {resp.json()}")
        return cdn_url

    # ----- Visual understanding -----

    def describe_image(
        self,
        image_path: str | Path,
        project: str = "",
    ) -> dict[str, Any]:
        """Look at a real ad creative and extract its visual DNA.

        This is the "look at the winner and describe why it works" path.
        Reuses the same upload + /chat + poll flow as evaluate_image, but the
        prompt asks for a structured visual description instead of a score.

        Returns parsed JSON describing the image's visual composition. Falls back
        to a {"error": ...} dict on parse failure (matches evaluate_image shape).
        """
        cdn_url = self.upload_file(image_path)

        desc_prompt = (
            "You are analyzing a real mobile game advertisement image that performed well on Facebook. "
            "Describe its visual DNA in detail so it can be used to generate variation creatives. "
            "Respond ONLY with a single JSON object, no markdown fences, no commentary, in this exact schema:\n"
            "{\n"
            '  "subject": "main subject in one phrase, e.g. witch character close-up",\n'
            '  "composition": "camera framing and layout, e.g. split-screen left/right, centered hero shot",\n'
            '  "palette": "dominant colors actually visible in this image",\n'
            '  "lighting": "light/shadow treatment, e.g. neon glow, dark moody, bright flat",\n'
            '  "ui_elements": ["merge board", "CTA button", ...],\n'
            '  "overlay_text": "exact or near-exact text overlay wording, empty string if none",\n'
            '  "cta_style": "placement and wording of the call-to-action, empty string if none",\n'
            '  "character_pose": "what the character is doing, empty if no character",\n'
            '  "mood": "emotional tone the image projects, e.g. urgent, satisfying, mysterious",\n'
            '  "hook_type": "one of: crisis, reward, twist, comparison, curiosity, collection, other",\n'
            '  "standout_features": ["2-4 specific things that make this ad eye-catching"],\n'
            '  "overall_summary": "one sentence on why this creative likely wins"\n'
            "}\n"
        )
        if project:
            desc_prompt = f"Project context: {project}.\n" + desc_prompt

        body = {
            "prompt": desc_prompt,
            "project_id": self.ensure_project(),
            "mode": "fast",
            "attachments": [cdn_url],
        }

        t0 = time.time()
        chat_resp = self._api_post("/chat", body)
        inner = chat_resp.get("data", chat_resp)
        thread_id = inner.get("thread_id", "") or chat_resp.get("thread_id", "")

        if not thread_id:
            return {"error": f"No thread_id: {chat_resp}"}

        result = self._poll_result(thread_id, t0)
        if result.status != "done":
            return {"error": f"Description failed: {result.status}", "assistant_text": result.assistant_text}

        parsed = self._parse_desc_text(result.assistant_text)
        parsed["_assistant_text"] = result.assistant_text[:500]
        parsed["_cdn_url"] = cdn_url
        return parsed

    @staticmethod
    def _parse_desc_text(text: str) -> dict[str, Any]:
        """Extract the visual-DNA JSON from Lovart's response.

        Lovart sometimes wraps JSON in ```json fences or adds prose around it.
        Try fenced block first, then bare JSON object, then give up gracefully.
        """
        import re

        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            try:
                return json.loads(fenced.group(1))
            except json.JSONDecodeError:
                pass

        bare = re.search(r"\{.*\}", text, re.DOTALL)
        if bare:
            try:
                return json.loads(bare.group(0))
            except json.JSONDecodeError:
                pass

        return {
            "error": "Could not parse visual DNA JSON from response",
            "raw_text": text[:500],
        }

    # ----- Evaluation -----

    def evaluate_image(
        self,
        image_path: str | Path,
        prompt: str,
        project: str = "",
        hook_type: str = "",
    ) -> dict[str, Any]:
        """Use Lovart AI to evaluate an image.

        Uploads the image and sends an evaluation prompt.
        Returns parsed JSON scores.
        """
        # Upload image to CDN
        cdn_url = self.upload_file(image_path)

        # Build evaluation prompt
        eval_prompt = (
            f"Evaluate this AI-generated mobile game ad creative for project '{project}'.\n"
            f"Intended hook type: {hook_type}\n"
            f"Generation prompt: {prompt}\n\n"
            "Score each dimension from 1 to 10 and respond ONLY in JSON format:\n"
            '{"visual_quality": <1-10>, "brand_alignment": <1-10>, '
            '"hook_clarity": <1-10>, "ad_suitability": <1-10>, '
            '"originality": <1-10>, '
            '"strengths": ["..."], "improvements": ["..."], '
            '"summary": "..."}'
        )

        body = {
            "prompt": eval_prompt,
            "project_id": self.ensure_project(),
            "mode": "fast",
            "attachments": [cdn_url],
        }

        # Submit and poll
        t0 = time.time()
        chat_resp = self._api_post("/chat", body)
        inner = chat_resp.get("data", chat_resp)
        thread_id = inner.get("thread_id", "") or chat_resp.get("thread_id", "")

        if not thread_id:
            return {"error": f"No thread_id: {chat_resp}"}

        # Poll for result
        result = self._poll_result(thread_id, t0)
        if result.status != "done":
            return {"error": f"Evaluation failed: {result.status}"}

        # Parse evaluation from assistant text
        return self._parse_eval_text(result.assistant_text)

    @staticmethod
    def _parse_eval_text(text: str) -> dict[str, Any]:
        """Extract JSON scores from Lovart evaluation response."""
        import re
        # Try to find JSON block in the response
        json_match = re.search(r'\{[^{}]*"visual_quality"[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Try parsing the whole text as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Fallback: extract numbers after dimension names
        scores = {}
        for dim in ("visual_quality", "brand_alignment", "hook_clarity",
                     "ad_suitability", "originality"):
            match = re.search(rf'{dim}["\s:]+([\d.]+)', text)
            if match:
                scores[dim] = float(match.group(1))

        if scores:
            scores["summary"] = text[:500]
            return scores

        return {"error": f"Could not parse evaluation: {text[:300]}"}

    # ----- Public API -----

    def generate_image(
        self,
        prompt: str,
        model: str | None = None,
        project_id: str | None = None,
        attachments: list[str] | None = None,
    ) -> LovartResult:
        """Generate an image using Lovart. Blocks until result is ready.

        Args:
            prompt: The image generation prompt text.
            model: Specific model tool name. If None, uses first configured model.
            project_id: Optional Lovart project ID. Auto-creates if None.
            attachments: Optional list of CDN URLs for reference images.

        Returns:
            LovartResult with image_urls populated.
        """
        if model is None:
            model = self._models[0] if self._models else ALLOWED_MODELS["nano_banana"]

        # Ensure we have a project_id
        if not project_id:
            project_id = self.ensure_project()

        # Build tool_config to prefer specific model
        tool_config: dict[str, Any] = {
            "prefer_tool_categories": {"IMAGE": [model]},
        }

        body: dict[str, Any] = {
            "prompt": prompt,
            "project_id": project_id,
            "mode": self._mode,
            "tool_config": tool_config,
        }
        if attachments:
            body["attachments"] = attachments

        # Step 1: Submit chat request
        t0 = time.time()
        chat_resp = self._api_post("/chat", body)

        # Response may wrap data in {"code": 0, "data": {...}}
        inner = chat_resp.get("data", chat_resp)
        thread_id = inner.get("thread_id", "") or chat_resp.get("thread_id", "")

        if not thread_id:
            return LovartResult(
                thread_id="",
                status="error",
                assistant_text=f"No thread_id in response: {json.dumps(chat_resp, ensure_ascii=False)}",
                elapsed_sec=time.time() - t0,
                raw=chat_resp,
            )

        # If response already has results (synchronous mode)
        final_status = inner.get("final_status", inner.get("status", ""))
        if final_status == "done" and inner.get("items"):
            return self._parse_result(inner, t0)

        # If pending_confirmation, auto-confirm then poll
        if inner.get("pending_confirmation"):
            pending = inner["pending_confirmation"]
            cost = pending.get("estimated_cost", 0)
            print(f"[Lovart] Auto-confirming initial request (cost={cost} credits)...")
            try:
                self._api_post("/chat/confirm", {"thread_id": thread_id})
            except Exception:
                pass

        # Step 2: Poll for result
        return self._poll_result(thread_id, t0)

    def generate_image_all_models(
        self,
        prompt: str,
        project_id: str | None = None,
    ) -> list[LovartResult]:
        """Generate the same prompt with all configured models (nano banana + gpt-2)."""
        results = []
        for model in self._models:
            result = self.generate_image(prompt, model=model, project_id=project_id)
            result.raw["_model_used"] = model
            results.append(result)
        return results

    # ----- Polling -----

    def _poll_result(self, thread_id: str, t0: float) -> LovartResult:
        """Poll GET /chat/result until done or timeout."""
        while True:
            elapsed = time.time() - t0
            if elapsed > _POLL_MAX_WAIT_SEC:
                return LovartResult(
                    thread_id=thread_id,
                    status="timeout",
                    assistant_text=f"Polling exceeded {_POLL_MAX_WAIT_SEC}s",
                    elapsed_sec=elapsed,
                )

            try:
                resp = self._api_get(f"/chat/result?thread_id={thread_id}")
            except Exception as exc:
                # Network error, retry
                print(f"[Lovart] Poll error: {exc}, retrying in {_POLL_INTERVAL_SEC}s...")
                time.sleep(_POLL_INTERVAL_SEC)
                continue

            # Unwrap data envelope
            inner = resp.get("data", resp)
            status = inner.get("final_status", inner.get("status", ""))

            # Check for pending confirmation (paid models like GPT Image 2)
            pending = inner.get("pending_confirmation")
            if pending:
                cost = pending.get("estimated_cost", 0)
                print(f"[Lovart] Auto-confirming (cost={cost} credits)...")
                try:
                    self._api_post("/chat/confirm", {"thread_id": thread_id})
                except Exception as conf_exc:
                    print(f"[Lovart] Confirm error: {conf_exc}")
                time.sleep(_POLL_INTERVAL_SEC)
                continue

            if status in ("done", "abort"):
                # Check if done but items are empty — might need to re-poll
                items = inner.get("items", [])
                if status == "done" and not items:
                    # Wait a bit more for artifacts to appear
                    time.sleep(_POLL_INTERVAL_SEC)
                    continue
                return self._parse_result(inner, t0)

            # Still running
            time.sleep(_POLL_INTERVAL_SEC)

    def _parse_result(self, resp: dict[str, Any], t0: float) -> LovartResult:
        """Extract image URLs and assistant text from API response."""
        image_urls: list[str] = []
        assistant_text = ""

        for item in resp.get("items", []):
            if item.get("type") == "assistant":
                assistant_text += item.get("text", "") + "\n"
            if item.get("type") == "generator":
                for artifact in item.get("artifacts", []):
                    if artifact.get("type") == "image":
                        url = artifact.get("content", "")
                        if url:
                            image_urls.append(url)

        # Also check 'downloaded' field
        for dl in resp.get("downloaded", []):
            if dl.get("type") == "image":
                url = dl.get("url", "")
                if url and url not in image_urls:
                    image_urls.append(url)

        return LovartResult(
            thread_id=resp.get("thread_id", ""),
            status=resp.get("final_status", resp.get("status", "unknown")),
            image_urls=image_urls,
            assistant_text=assistant_text.strip(),
            project_id=resp.get("project_id", ""),
            elapsed_sec=time.time() - t0,
            raw=resp,
        )

    # ----- HTTP helpers -----

    def _sign(self, method: str, path: str) -> dict[str, str]:
        """Generate HMAC-SHA256 signature headers."""
        ts = str(int(time.time()))
        message = f"{method}\n{path}\n{ts}"
        sig = hmac.new(
            self._sk.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-Access-Key": self._ak,
            "X-Timestamp": ts,
            "X-Signature": sig,
            "X-Signed-Method": method,
            "X-Signed-Path": path,
        }

    def _api_post(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST to Lovart API with auth."""
        path = f"{_API_PREFIX}{endpoint}"
        url = f"{self._base}{path}"

        headers = self._sign("POST", path)
        headers.update({
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
            "Idempotency-Key": str(uuid.uuid4()),
        })

        return self._do_request("POST", url, headers, json=body)

    def _api_get(self, endpoint: str) -> dict[str, Any]:
        """GET from Lovart API with auth."""
        path = f"{_API_PREFIX}{endpoint}"
        url = f"{self._base}{path}"

        headers = self._sign("GET", path)
        headers.update({
            "User-Agent": _USER_AGENT,
        })

        return self._do_request("GET", url, headers)

    @staticmethod
    def _do_request(
        method: str,
        url: str,
        headers: dict[str, str],
        json: dict[str, Any] | None = None,
        retries: int = 3,
    ) -> dict[str, Any]:
        """Execute HTTP request with retries using requests library."""
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                resp = _requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json,
                    timeout=60,
                    verify=False,
                )
                if resp.status_code >= 400:
                    raise RuntimeError(f"Lovart API {resp.status_code}: {resp.text}")
                return resp.json() if resp.text else {}
            except RuntimeError:
                raise  # Don't retry auth/billing errors
            except Exception as exc:
                last_err = exc
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"Lovart API request failed after {retries} attempts: {last_err}")


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------
def download_image(url: str, dest_path: str | Path, timeout: int = 120) -> Path:
    """Download an image from URL to local path."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        resp = _requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=timeout, stream=True)
        resp.raise_for_status()
    except _requests.exceptions.SSLError:
        # Retry without SSL verification for hosts with TLS issues
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        resp = _requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=timeout,
                            stream=True, verify=False)
        resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest
