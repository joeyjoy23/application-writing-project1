"""
多阶段 AI 工作流：Stage1 → Stage2 → Stage3 → Stage4
Prompt 从 prompts/ 目录动态加载。
"""

from __future__ import annotations

import json
from collections.abc import Callable

from llm.client import RunCancelled
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ProgressFn = Callable[[str], None] | None
StreamFn = Callable[[str, int, str], None] | None
CancelFn = Callable[[], bool] | None

from llm.client import LLMClient
from utils.config import get_project_root
from utils.parsers import parse_stage1_output

PROMPTS_DIR = get_project_root() / "prompts"

MAX_CHARS_FOR_STAGE4 = 10000


def _trim_text(text: str, limit: int, label: str) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    half = limit // 2
    return (
        f"{text[:half]}\n\n"
        f"……（{label} 中段已省略，共约 {len(text)} 字）……\n\n"
        f"{text[-half:]}"
    )


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    return path.read_text(encoding="utf-8").strip()


@dataclass
class Stage1Result:
    raw: str
    structured_json: dict[str, Any]
    human_summary: str


@dataclass
class Stage2Result:
    raw: str


@dataclass
class Stage3Result:
    raw: str


@dataclass
class Stage4Result:
    raw: str


@dataclass
class WorkflowState:
    question: str = ""
    stage1: Stage1Result | None = None
    stage2: Stage2Result | None = None
    stage3: Stage3Result | None = None
    stage4: Stage4Result | None = None
    errors: list[str] = field(default_factory=list)


class GaokaoWritingWorkflow:
    def __init__(self, client: LLMClient | None = None):
        self.client = client or LLMClient()
        self._system = load_prompt("system_prompt.md")

    def run_stage1(
        self,
        question: str,
        on_progress: ProgressFn = None,
        on_stream: StreamFn = None,
        should_cancel: CancelFn = None,
    ) -> Stage1Result:
        user = (
            f"【应用文原题】\n\n{question.strip()}\n\n"
            "请按 stage1 任务说明输出 STRUCTURED_JSON 与 HUMAN_READABLE_SUMMARY。"
        )
        stage_prompt = load_prompt("stage1_prompt.md")

        def _stream(_d: str, total: int, full: str) -> None:
            if on_stream:
                on_stream(_d, total, full)

        if on_progress:
            on_progress(f"Calling API (model: {self.client.settings.model})…")
        raw = self.client.chat(
            system=f"{self._system}\n\n---\n\n{stage_prompt}",
            user=user,
            max_tokens=3072,
            on_stream=_stream,
            should_cancel=should_cancel,
        )
        structured, summary = parse_stage1_output(raw)
        return Stage1Result(raw=raw, structured_json=structured, human_summary=summary)

    def run_stage2(
        self,
        question: str,
        stage1_json: dict[str, Any],
        on_progress: ProgressFn = None,
        on_stream: StreamFn = None,
        should_cancel: CancelFn = None,
    ) -> Stage2Result:
        user = (
            f"【原题】\n\n{question.strip()}\n\n"
            f"【Stage1 JSON】\n\n```json\n{json.dumps(stage1_json, ensure_ascii=False, indent=2)}\n```\n\n"
            "请按 stage2 任务说明完成 PEEL 写作策略卡与多版范文（不含句型包与词汇锦囊）。"
        )
        stage_prompt = load_prompt("stage2_prompt.md")

        def _stream(_d: str, total: int, full: str) -> None:
            if on_stream:
                on_stream(_d, total, full)

        if on_progress:
            on_progress(f"Calling API Stage 2 (model: {self.client.settings.model})…")
        raw = self.client.chat(
            system=f"{self._system}\n\n---\n\n{stage_prompt}",
            user=user,
            max_tokens=6144,
            on_stream=_stream,
            should_cancel=should_cancel,
        )
        return Stage2Result(raw=raw)

    def run_stage3(
        self,
        question: str,
        stage1_json: dict[str, Any],
        on_progress: ProgressFn = None,
        on_stream: StreamFn = None,
        should_cancel: CancelFn = None,
    ) -> Stage3Result:
        user = (
            f"【原题】\n\n{question.strip()}\n\n"
            f"【Stage1 JSON】\n\n```json\n{json.dumps(stage1_json, ensure_ascii=False, indent=2)}\n```\n\n"
            "请按 stage3 任务说明输出功能句型包与话题词汇锦囊。"
        )
        stage_prompt = load_prompt("stage3_prompt.md")

        def _stream(_d: str, total: int, full: str) -> None:
            if on_stream:
                on_stream(_d, total, full)

        if on_progress:
            on_progress(f"Calling API Stage 3 (model: {self.client.settings.model})…")
        raw = self.client.chat(
            system=f"{self._system}\n\n---\n\n{stage_prompt}",
            user=user,
            max_tokens=4096,
            on_stream=_stream,
            should_cancel=should_cancel,
        )
        return Stage3Result(raw=raw)

    def run_stage4(
        self,
        stage1_json: dict[str, Any],
        stage2_output: str,
        stage3_output: str,
        on_progress: ProgressFn = None,
        on_stream: StreamFn = None,
        should_cancel: CancelFn = None,
    ) -> Stage4Result:
        s2 = _trim_text(stage2_output, MAX_CHARS_FOR_STAGE4 // 2, "Stage2")
        s3 = _trim_text(stage3_output, MAX_CHARS_FOR_STAGE4 // 2, "Stage3")
        user = (
            f"【Stage1 JSON】\n\n```json\n{json.dumps(stage1_json, ensure_ascii=False, indent=2)}\n```\n\n"
            f"【Stage2 输出（PEEL 与范文）】\n\n{s2}\n\n"
            f"【Stage3 输出（句型与词汇）】\n\n{s3}\n\n"
            "请按 stage4 任务说明输出教学指南与易错预警。"
        )
        stage_prompt = load_prompt("stage4_prompt.md")

        def _stream(_d: str, total: int, full: str) -> None:
            if on_stream:
                on_stream(_d, total, full)

        if on_progress:
            on_progress(f"Calling API Stage 4 (model: {self.client.settings.model})…")
        raw = self.client.chat(
            system=f"{self._system}\n\n---\n\n{stage_prompt}",
            user=user,
            max_tokens=4096,
            on_stream=_stream,
            should_cancel=should_cancel,
        )
        return Stage4Result(raw=raw)

    def run_full_pipeline(self, question: str) -> WorkflowState:
        state = WorkflowState(question=question)
        try:
            state.stage1 = self.run_stage1(question)
        except Exception as e:
            state.errors.append(f"Stage1 失败: {e}")
            return state

        try:
            state.stage2 = self.run_stage2(question, state.stage1.structured_json)
        except Exception as e:
            state.errors.append(f"Stage2 失败: {e}")
            return state

        try:
            state.stage3 = self.run_stage3(question, state.stage1.structured_json)
        except Exception as e:
            state.errors.append(f"Stage3 失败: {e}")
            return state

        try:
            state.stage4 = self.run_stage4(
                state.stage1.structured_json,
                state.stage2.raw,
                state.stage3.raw,
            )
        except Exception as e:
            state.errors.append(f"Stage4 失败: {e}")

        return state
