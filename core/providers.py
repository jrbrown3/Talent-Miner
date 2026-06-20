"""Configurable AI provider layer.

A single ``AIProvider`` interface with concrete implementations for Ollama,
Claude, OpenAI and OpenAI-via-Azure. A ``Demo (offline)`` provider is included
so the app is fully runnable with no API keys and no network.

All third-party SDKs are imported lazily so that the app starts even when an
individual SDK is not installed - you only need the package for the provider
you actually use.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any


class ProviderError(RuntimeError):
    """Raised when a provider cannot be configured or a call fails."""


class AIProvider(ABC):
    name: str = "base"

    def __init__(self, model: str, temperature: float = 0.2):
        self.model = model
        self.temperature = temperature

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str,
                 json_mode: bool = True) -> str:
        """Return the model's text response for the given prompts.

        When ``json_mode`` is True the provider asks the model for a JSON object
        (used for the opportunity analysis). Set it False for free-form markdown
        (used for the use-case document builder).
        """

    def check(self) -> tuple[bool, str]:
        """Lightweight connectivity / credential check. (ok, message)."""
        return True, "ok"


# ---------------------------------------------------------------------------

class DemoProvider(AIProvider):
    """Offline, deterministic provider. Produces plausible opportunities from
    keyword heuristics so the UI can be exercised end-to-end without any model.
    """

    name = "Demo (offline)"

    # keyword -> opportunity template
    RULES: list[dict[str, Any]] = [
        {"kw": ["report", "reporting", "dashboard", "presentation", "powerpoint", "deck"],
         "title": "Automated reporting & narrative generation",
         "category": "Reporting & Analytics", "pattern": "automation",
         "impact": 4, "effort": 2,
         "ctx": "Recurring reports and summaries can be drafted automatically from "
                "source data, with an analyst reviewing rather than authoring from scratch.",
         "tools": ["LLM summarization", "Templated generation"]},
        {"kw": ["email", "correspondence", "communicate", "stakeholder", "client"],
         "title": "Drafting and triage of routine communications",
         "category": "Communication", "pattern": "augmentation",
         "impact": 3, "effort": 1,
         "ctx": "First-draft emails and message triage can be assisted by AI, letting "
                "the role focus on judgment-heavy responses.",
         "tools": ["LLM drafting", "Classification"]},
        {"kw": ["data", "spreadsheet", "excel", "analysis", "analyse", "analyze", "model"],
         "title": "Assisted data cleaning and exploratory analysis",
         "category": "Data & Analysis", "pattern": "augmentation",
         "impact": 4, "effort": 3,
         "ctx": "AI can accelerate data wrangling, anomaly spotting and first-pass "
                "analysis, leaving validation and interpretation to the specialist.",
         "tools": ["Code generation", "Tabular reasoning"]},
        {"kw": ["research", "review", "document", "compliance", "policy", "contract"],
         "title": "Document review and information extraction",
         "category": "Document Processing", "pattern": "automation",
         "impact": 4, "effort": 3,
         "ctx": "Long documents can be summarized and key fields extracted automatically, "
                "with a human confirming anything material or high-risk.",
         "tools": ["RAG", "Entity extraction"]},
        {"kw": ["schedule", "calendar", "coordinate", "plan", "meeting"],
         "title": "Scheduling and coordination assistance",
         "category": "Operations", "pattern": "automation",
         "impact": 2, "effort": 1,
         "ctx": "Routine scheduling and follow-up coordination can be largely automated.",
         "tools": ["Agentic assistant"]},
        {"kw": ["customer", "support", "ticket", "inquiry", "faq"],
         "title": "Customer / internal support deflection",
         "category": "Support", "pattern": "augmentation",
         "impact": 3, "effort": 2,
         "ctx": "An AI assistant grounded in internal knowledge can answer common "
                "questions and draft responses for human approval.",
         "tools": ["RAG chatbot"]},
        {"kw": ["code", "develop", "software", "script", "automation", "pipeline"],
         "title": "Code generation and review assistance",
         "category": "Engineering", "pattern": "augmentation",
         "impact": 4, "effort": 2,
         "ctx": "Boilerplate, tests and first-pass reviews can be AI-assisted to "
                "increase throughput.",
         "tools": ["Code assistant"]},
        {"kw": ["forecast", "trading", "risk", "portfolio", "market", "quantitative"],
         "title": "Signal research and back-test scaffolding assistance",
         "category": "Quant & Strategy", "pattern": "augmentation",
         "impact": 5, "effort": 4,
         "ctx": "AI can accelerate hypothesis generation, feature ideas and back-test "
                "scaffolding, with all signals validated under existing risk controls.",
         "tools": ["Code generation", "Literature synthesis"]},
    ]

    def complete(self, system_prompt: str, user_prompt: str,
                 json_mode: bool = True) -> str:
        # Use-case builder asks for markdown (json_mode=False); produce a brief.
        if not json_mode:
            return self._use_case_markdown(user_prompt)
        text = user_prompt.lower()
        # Pull the JD body out of the analysis prompt so demo evidence is grounded.
        m = re.search(r'JOB DESCRIPTION:\s*"""(.*?)"""', user_prompt, re.DOTALL)
        jd_body = m.group(1) if m else user_prompt
        jd_lines = [ln.strip() for ln in jd_body.splitlines() if len(ln.strip()) > 8]

        def _evidence_for(kws: list[str]) -> list[str]:
            for ln in jd_lines:
                low = ln.lower()
                if any(k in low for k in kws):
                    return [ln[:200]]
            return []

        chosen: list[dict[str, Any]] = []
        for rule in self.RULES:
            if any(kw in text for kw in rule["kw"]):
                chosen.append(rule)
        if not chosen:
            chosen = self.RULES[:3]
        seen = set()
        opportunities = []
        for r in chosen:
            if r["title"] in seen:
                continue
            seen.add(r["title"])
            impact = r["impact"]
            confidence = "high" if impact >= 4 else "medium" if impact == 3 else "low"
            opportunities.append({
                "title": r["title"],
                "category": r["category"],
                "context": r["ctx"],
                "ai_pattern": r["pattern"],
                "impact": impact,
                "impact_rationale": "Heuristic estimate (demo provider).",
                "effort": r["effort"],
                "effort_rationale": "Heuristic estimate (demo provider).",
                "confidence": confidence,
                "evidence": _evidence_for(r["kw"]),
                "est_weekly_hours_saved": round(impact * 1.5, 1),
                "example_tools": r["tools"],
            })
        return json.dumps({"role_summary": "Demo analysis (offline heuristic).",
                           "opportunities": opportunities})

    @staticmethod
    def _use_case_markdown(user_prompt: str) -> str:
        """Offline templated use-case brief built from the prompt's fields."""
        import re

        def grab(label: str, default: str = "—") -> str:
            m = re.search(rf"{label}:\s*(.+)", user_prompt)
            return m.group(1).strip() if m else default

        title = grab("Title", "AI Use Case")
        category = grab("Category", "General")
        pattern = grab("AI pattern", "augmentation")
        impact = grab("Impact", "3")
        effort = grab("Effort", "3")
        role = grab("Role", "the role")
        context = grab("Context", "")
        return f"""# {title}

*Demo brief generated offline — switch to a real model in Settings for a tailored document.*

## Executive summary
This is an **{pattern}** opportunity in the **{category}** area for {role}. {context}

## Problem / current state
The relevant tasks are currently performed manually, consuming time that could be redirected
to higher-value work. This brief outlines how AI could address that.

## Proposed AI solution
Apply an {pattern} approach so the work is {'performed by AI with human oversight' if pattern.strip()=='automation' else 'accelerated with AI assisting a human'}.

## How it works
1. Capture the relevant inputs (documents, data, or messages).
2. Apply the AI model / technique to draft or process the work.
3. Route results to a human for review and approval where needed.

## Expected business impact
Estimated impact rating of **{impact}/5**. Benefits include time savings, faster turnaround,
and improved consistency.

## Implementation considerations
Estimated effort rating of **{effort}/5**. Consider data access, model selection, integration
points, and a human-in-the-loop review step.

## Risks & mitigations
- **Quality / accuracy** — keep a human review step until confidence is established.
- **Data privacy** — ensure inputs are handled per policy.

## Success metrics
- Time saved per task
- Throughput / cycle time
- Quality / rework rate

## Next steps
Run a small proof of concept on a representative sample, then evaluate against the success
metrics before scaling.
"""


# ---------------------------------------------------------------------------

class OllamaProvider(AIProvider):
    name = "Ollama"

    def __init__(self, model: str, temperature: float = 0.2,
                 base_url: str = "http://localhost:11434"):
        super().__init__(model, temperature)
        self.base_url = base_url.rstrip("/")

    def complete(self, system_prompt: str, user_prompt: str,
                 json_mode: bool = True) -> str:
        import requests

        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": self.temperature},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            payload["format"] = "json"
        try:
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=300)
            resp.raise_for_status()
        except Exception as exc:  # pragma: no cover - network dependent
            raise ProviderError(f"Ollama request failed: {exc}") from exc
        return resp.json().get("message", {}).get("content", "")

    def check(self) -> tuple[bool, str]:
        import requests

        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            return True, f"Connected to Ollama at {self.base_url}"
        except Exception as exc:
            return False, f"Cannot reach Ollama at {self.base_url}: {exc}"


class ClaudeProvider(AIProvider):
    name = "Claude"

    def __init__(self, model: str, api_key: str, temperature: float = 0.2):
        super().__init__(model, temperature)
        if not api_key:
            raise ProviderError("Missing Anthropic API key.")
        self.api_key = api_key

    def complete(self, system_prompt: str, user_prompt: str,
                 json_mode: bool = True) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderError("anthropic package not installed (pip install anthropic).") from exc
        client = anthropic.Anthropic(api_key=self.api_key)
        try:
            msg = client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=self.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:  # pragma: no cover
            raise ProviderError(f"Claude request failed: {exc}") from exc
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


class OpenAIProvider(AIProvider):
    name = "OpenAI"

    def __init__(self, model: str, api_key: str, temperature: float = 0.2):
        super().__init__(model, temperature)
        if not api_key:
            raise ProviderError("Missing OpenAI API key.")
        self.api_key = api_key

    def _client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError("openai package not installed (pip install openai).") from exc
        return OpenAI(api_key=self.api_key)

    def complete(self, system_prompt: str, user_prompt: str,
                 json_mode: bool = True) -> str:
        client = self._client()
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **kwargs,
            )
        except Exception as exc:  # pragma: no cover
            raise ProviderError(f"OpenAI request failed: {exc}") from exc
        return resp.choices[0].message.content or ""


class AzureOpenAIProvider(AIProvider):
    name = "OpenAI via Azure"

    def __init__(self, deployment: str, api_key: str, endpoint: str,
                 api_version: str = "2024-06-01", temperature: float = 0.2):
        super().__init__(deployment, temperature)
        if not api_key:
            raise ProviderError("Missing Azure OpenAI API key.")
        if not endpoint:
            raise ProviderError("Missing Azure OpenAI endpoint.")
        self.api_key = api_key
        self.endpoint = endpoint
        self.api_version = api_version

    def complete(self, system_prompt: str, user_prompt: str,
                 json_mode: bool = True) -> str:
        try:
            from openai import AzureOpenAI
        except ImportError as exc:
            raise ProviderError("openai package not installed (pip install openai).") from exc
        client = AzureOpenAI(api_key=self.api_key, azure_endpoint=self.endpoint,
                             api_version=self.api_version)
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = client.chat.completions.create(
                model=self.model,  # this is the Azure deployment name
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **kwargs,
            )
        except Exception as exc:  # pragma: no cover
            raise ProviderError(f"Azure OpenAI request failed: {exc}") from exc
        return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------

def build_provider(cfg: dict[str, Any], api_key: str = "") -> AIProvider:
    """Factory that turns the config dict into a concrete provider."""
    provider = cfg.get("provider", "Demo (offline)")
    temperature = float(cfg.get("temperature", 0.2))
    models = cfg.get("models", {})

    if provider == "Demo (offline)":
        return DemoProvider(model="demo", temperature=temperature)
    if provider == "Ollama":
        return OllamaProvider(models.get("Ollama", "llama3.1"), temperature,
                              cfg.get("ollama_base_url", "http://localhost:11434"))
    if provider == "Claude":
        return ClaudeProvider(models.get("Claude", "claude-sonnet-4-6"), api_key, temperature)
    if provider == "OpenAI":
        return OpenAIProvider(models.get("OpenAI", "gpt-4o"), api_key, temperature)
    if provider == "OpenAI via Azure":
        deployment = cfg.get("azure_deployment") or models.get("OpenAI via Azure", "gpt-4o")
        return AzureOpenAIProvider(deployment, api_key, cfg.get("azure_endpoint", ""),
                                   cfg.get("azure_api_version", "2024-06-01"), temperature)
    raise ProviderError(f"Unknown provider: {provider}")


def extract_json(text: str) -> dict[str, Any]:
    """Robustly pull a JSON object out of a model response."""
    if not text or not text.strip():
        raise ProviderError("Empty response from model.")
    # strip markdown fences if present
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # fall back to the first balanced-looking object
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(candidate[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Could not parse JSON from model output: {exc}") from exc
    raise ProviderError("Model did not return JSON.")
