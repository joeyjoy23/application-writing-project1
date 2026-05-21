import json
import re
from typing import Any


JSON_MARKER = "===STRUCTURED_JSON==="
SUMMARY_MARKER = "===HUMAN_READABLE_SUMMARY==="

_PART_B_SPLIT = re.compile(
    r"#?\s*PART\s*B[：:]\s*HUMAN_READABLE_SUMMARY\s*",
    re.IGNORECASE,
)


def parse_stage1_output(raw: str) -> tuple[dict[str, Any], str]:
    """从 Stage1 模型输出中解析 JSON 与人类可读摘要。"""
    text = raw.strip()

    if JSON_MARKER in text and SUMMARY_MARKER in text:
        _, _, rest = text.partition(JSON_MARKER)
        after_json, _, summary_part = rest.partition(SUMMARY_MARKER)
        structured = _extract_json(after_json.strip())
        return structured, clean_stage1_summary(summary_part)

    part_b_split = _PART_B_SPLIT.split(text, maxsplit=1)
    if len(part_b_split) == 2:
        structured = _extract_json_from_part_a(part_b_split[0])
        summary = clean_stage1_summary(part_b_split[1])
        return structured, summary

    code_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_match:
        structured = _extract_json(code_match.group(1).strip())
        summary = _PART_B_SPLIT.sub("", text)
        summary = re.sub(r"```(?:json)?\s*[\s\S]*?```", "", summary)
        return structured, clean_stage1_summary(summary)

    return {}, clean_stage1_summary(text)


def clean_stage1_summary(summary: str) -> str:
    """去掉 PART A / JSON 等，仅保留教师可读的审题总结。"""
    text = summary.strip()
    text = re.sub(
        r"#?\s*PART\s*A[：:]\s*STRUCTURED_JSON[\s\S]*?(?=#?\s*PART\s*B|$)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = _PART_B_SPLIT.sub("", text)
    text = re.sub(r"```(?:json)?\s*[\s\S]*?```", "", text)
    text = re.sub(r"^#+\s*PART\s*[AB][：:][^\n]*\n?", "", text, flags=re.IGNORECASE | re.MULTILINE)
    return text.strip()


def _extract_json_from_part_a(text: str) -> dict[str, Any]:
    return _extract_json(text)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}

    fenced = re.match(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return {"_parse_error": True, "_raw": text[:2000]}
