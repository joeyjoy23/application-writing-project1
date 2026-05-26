"""LLM 调用用量统计。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChatUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0

    def merge(self, other: "ChatUsage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.cached_tokens += other.cached_tokens


@dataclass
class ChatResponse:
    text: str
    usage: ChatUsage = field(default_factory=ChatUsage)
