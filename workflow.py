"""
多阶段 AI 工作流：Stage1 → Stage2 → Stage3 → Stage4
Prompt 从 prompts/ 目录动态加载。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llm.client import LLMClient
from llm.usage import ChatUsage
from utils.config import get_project_root
from utils.llm_messages import (
    build_chat_messages,
    shared_question_context,
)
from utils.parsers import parse_stage1_output
from utils.stage4_input import build_stage4_user_sections

PROMPTS_DIR = get_project_root() / "prompts"


from functools import lru_cache


@lru_cache(maxsize=8)
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


ProgressFn = Callable[[str], None] | None
StreamFn = Callable[[str, int, str], None] | None
CancelFn = Callable[[], bool] | None


class GaokaoWritingWorkflow:
    def __init__(self, client: LLMClient | None = None):
        self.client = client or LLMClient()
        self._system = load_prompt("system_prompt.md")
        self.last_usage: ChatUsage = ChatUsage()

    def _call(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        on_progress: ProgressFn = None,
        on_stream: StreamFn = None,
        should_cancel: CancelFn = None,
        progress_label: str = "Calling API",
    ) -> str:
        if on_progress:
            on_progress(
                f"{progress_label} (model: {self.client.settings.model})…"
            )

        def _stream(_d: str, total: int, full: str) -> None:
            if on_stream:
                on_stream(_d, total, full)

        resp = self.client.chat_with_messages(
            messages,
            max_tokens=max_tokens,
            on_stream=_stream,
            should_cancel=should_cancel,
        )
        self.last_usage = resp.usage
        return resp.text

    def run_stage1(
        self,
        question: str,
        on_progress: ProgressFn = None,
        on_stream: StreamFn = None,
        should_cancel: CancelFn = None,
    ) -> Stage1Result:
        stage_prompt = load_prompt("stage1_prompt.md")
        messages = build_chat_messages(
            system_base=self._system,
            stage_prompt=stage_prompt,
            user_parts=[
                f"【应用文原题】\n\n{question.strip()}",
                "请按 stage1 任务说明输出 STRUCTURED_JSON 与 HUMAN_READABLE_SUMMARY。",
            ],
        )
        raw = self._call(
            messages,
            max_tokens=3072,
            on_progress=on_progress,
            on_stream=on_stream,
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
        stage_prompt = load_prompt("stage2_prompt.md")
        json_text = json.dumps(stage1_json, ensure_ascii=False, indent=2)
        messages = build_chat_messages(
            system_base=self._system,
            stage_prompt=stage_prompt,
            user_parts=[
                shared_question_context(question, json_text),
                "请按 stage2 任务说明完成 PEEL 写作策略卡与多版范文（不含句型包与词汇锦囊）。",
            ],
        )
        raw = self._call(
            messages,
            max_tokens=6144,
            on_progress=on_progress,
            on_stream=on_stream,
            should_cancel=should_cancel,
            progress_label="Calling API Stage 2",
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
        stage_prompt = load_prompt("stage3_prompt.md")
        json_text = json.dumps(stage1_json, ensure_ascii=False, indent=2)
        messages = build_chat_messages(
            system_base=self._system,
            stage_prompt=stage_prompt,
            user_parts=[
                shared_question_context(question, json_text),
                "请按 stage3 任务说明输出功能句型包与话题词汇锦囊。",
            ],
        )
        raw = self._call(
            messages,
            max_tokens=4096,
            on_progress=on_progress,
            on_stream=on_stream,
            should_cancel=should_cancel,
            progress_label="Calling API Stage 3",
        )
        return Stage3Result(raw=raw)

    def run_stage4(
        self,
        stage1_json: dict[str, Any],
        stage2_output: str,
        stage3_output: str,
        *,
        student_level: str = "中等",
        on_progress: ProgressFn = None,
        on_stream: StreamFn = None,
        should_cancel: CancelFn = None,
    ) -> Stage4Result:
        level = (
            student_level
            if student_level in ("基础", "中等", "进阶")
            else "中等"
        )
        stage_prompt = load_prompt("stage4_prompt.md").replace(
            "[student_level]", level
        )
        json_block, s2, s3 = build_stage4_user_sections(
            stage1_json, stage2_output, stage3_output
        )
        messages = build_chat_messages(
            system_base=self._system,
            stage_prompt=stage_prompt,
            user_parts=[
                f"当前学生水平：{level}",
                f"student_level：{level}",
                f"【Stage1 JSON】\n\n```json\n{json_block}\n```",
                f"【Stage2 输出（PEEL 与范文）】\n\n{s2}",
                f"【Stage3 输出（句型与词汇）】\n\n{s3}",
                "请按 stage4 任务说明输出教学指南与易错预警。",
            ],
        )
        raw = self._call(
            messages,
            max_tokens=4096,
            on_progress=on_progress,
            on_stream=on_stream,
            should_cancel=should_cancel,
            progress_label="Calling API Stage 4",
        )
        return Stage4Result(raw=raw)

    def run_full_pipeline(
        self, question: str, *, student_level: str = "中等"
    ) -> WorkflowState:
        from concurrent.futures import ThreadPoolExecutor, wait

        state = WorkflowState(question=question)
        try:
            state.stage1 = self.run_stage1(question)
        except Exception as e:
            state.errors.append(f"Stage1 失败: {e}")
            return state

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                f2 = pool.submit(
                    self.run_stage2, question, state.stage1.structured_json
                )
                f3 = pool.submit(
                    self.run_stage3, question, state.stage1.structured_json
                )
                done, _ = wait([f2, f3])
                errors = []
                for fut in done:
                    exc = fut.exception()
                    if exc:
                        errors.append(exc)
                if errors:
                    raise RuntimeError(f"Stage2/3 共 {len(errors)} 个阶段失败") from errors[0]
                state.stage2 = f2.result()
                state.stage3 = f3.result()
        except Exception as e:
            state.errors.append(f"Stage2/3 失败: {e}")
            return state

        try:
            state.stage4 = self.run_stage4(
                state.stage1.structured_json,
                state.stage2.raw,
                state.stage3.raw,
                student_level=student_level,
            )
        except Exception as e:
            state.errors.append(f"Stage4 失败: {e}")

        return state
