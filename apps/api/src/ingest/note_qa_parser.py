from __future__ import annotations

import hashlib
import json
import re
from typing import TypedDict


class QACard(TypedDict):
    question_id: str
    question: str
    standard_answer: str
    topic: str
    topic_group: str
    tags: list[str]
    difficulty: str
    key_points: list[str]


_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
_QUESTION_RE = re.compile(r"^###\s*(\d+)[）\)]\s*(.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_+#.]+|[\u4e00-\u9fff]{2,}")


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _clean_markdown_inline(text: str) -> str:
    value = text.replace("`", "")
    value = value.replace("**", "")
    value = value.replace("*", "")
    return value.strip()


def _topic_from_section(section: str) -> str:
    s = section.lower()
    if "语言基础" in section or "语法" in section:
        return "java_basic"
    if "面向对象" in section or "设计模式" in section:
        return "oop_design"
    if "集合" in section or "数据结构" in section:
        return "collections"
    if "反射" in section or "aop" in s or "代理" in section:
        return "reflection_aop"
    if "线程" in section or "并发" in section:
        return "concurrency"
    if "jvm" in s or "内存" in section:
        return "jvm_memory"
    if "数据库" in section or "sql" in s:
        return "database"
    return "general"


def _tags_from_text(*parts: str) -> list[str]:
    text = " ".join(parts).lower()
    mapping = {
        "hashmap": ["hashmap", "hash map"],
        "concurrenthashmap": ["concurrenthashmap", "concurrent hash map"],
        "thread": ["线程", "并发", "thread", "volatile", "cas", "lock"],
        "aop": ["aop", "动态代理", "cglib", "jdk 动态代理", "jdk动态代理"],
        "jvm": ["jvm", "内存", "oom", "垃圾回收", "gc"],
        "collection": ["集合", "list", "set", "map", "arraylist", "linkedlist", "treemap"],
        "design_pattern": ["设计模式", "单例", "工厂", "策略", "责任链", "模板方法"],
        "java_basic": ["integer", "int", "equals", "hashcode", "jdk", "jre", "getclass"],
    }
    out: list[str] = []
    for tag, hints in mapping.items():
        if any(h in text for h in hints):
            out.append(tag)
    return out


def _difficulty_from_question(question: str) -> str:
    q = question.lower()
    hard_hints = [
        "原理",
        "实现",
        "并发",
        "线程安全",
        "扩容",
        "aop",
        "jvm",
        "排查",
        "hashmap",
        "concurrenthashmap",
    ]
    easy_hints = ["什么是", "区别", "介绍", "定义", "作用"]
    if any(h in q for h in hard_hints):
        return "hard"
    if any(h in q for h in easy_hints):
        return "easy"
    return "medium"


def _extract_key_points(answer: str, limit: int = 6) -> list[str]:
    points: list[str] = []
    for line in answer.splitlines():
        m = _BULLET_RE.match(line)
        if not m:
            continue
        item = _clean_markdown_inline(m.group(1))
        if item:
            points.append(item)
        if len(points) >= limit:
            break
    if points:
        return points

    cleaned = _clean_markdown_inline(answer)
    chunks = re.split(r"[。！？；;\n]+", cleaned)
    for chunk in chunks:
        c = _normalize_space(chunk)
        if len(c) >= 8:
            points.append(c)
        if len(points) >= min(4, limit):
            break
    return points


def _stable_question_id(source_id: str, question: str) -> str:
    digest = hashlib.sha1(f"{source_id}:{question}".encode("utf-8")).hexdigest()[:10]
    return f"qa_{source_id}_{digest}"


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


def _dedupe_cards(cards: list[QACard]) -> list[QACard]:
    seen: set[str] = set()
    out: list[QACard] = []
    for card in cards:
        q_key = _normalize_space(card["question"]).lower()
        if q_key in seen:
            continue
        seen.add(q_key)
        out.append(card)
    return out


def parse_note_to_qa_cards(text: str, *, source_id: str) -> list[QACard]:
    if not text.strip():
        return []

    cards: list[QACard] = []
    current_section = "general"
    current_question = ""
    current_answer_lines: list[str] = []

    def flush_question():
        nonlocal current_question, current_answer_lines
        question = _normalize_space(current_question)
        answer = "\n".join(current_answer_lines).strip()
        current_question = ""
        current_answer_lines = []
        if not question or not answer:
            return
        key_points = _extract_key_points(answer)
        topic = _topic_from_section(current_section)
        tags = _tags_from_text(current_section, question, " ".join(key_points))
        cards.append(
            QACard(
                question_id=_stable_question_id(source_id, question),
                question=question,
                standard_answer=answer,
                topic=topic,
                topic_group=current_section,
                tags=tags,
                difficulty=_difficulty_from_question(question),
                key_points=key_points,
            )
        )

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        section_match = _SECTION_RE.match(line)
        if section_match:
            flush_question()
            current_section = _normalize_space(section_match.group(1))
            continue

        question_match = _QUESTION_RE.match(line)
        if question_match:
            flush_question()
            current_question = _normalize_space(question_match.group(2))
            continue

        if current_question:
            current_answer_lines.append(raw_line)

    flush_question()
    return _dedupe_cards(cards)


def build_qa_card_document(card: QACard) -> str:
    tags = ", ".join(card["tags"]) if card["tags"] else ""
    key_points = "\n".join(f"- {point}" for point in card["key_points"])
    return (
        f"Question: {card['question']}\n"
        f"StandardAnswer:\n{card['standard_answer']}\n\n"
        f"Topic: {card['topic']}\n"
        f"TopicGroup: {card['topic_group']}\n"
        f"Difficulty: {card['difficulty']}\n"
        f"Tags: {tags}\n"
        f"KeyPoints:\n{key_points}"
    )


def metadata_for_qa_card(card: QACard) -> dict:
    return {
        "doc_kind": "qa_card",
        "question_id": card["question_id"],
        "question": card["question"],
        "standard_answer": card["standard_answer"],
        "topic": card["topic"],
        "topic_group": card["topic_group"],
        "difficulty": card["difficulty"],
        "tags": ",".join(card["tags"]),
        "key_points_json": json.dumps(card["key_points"], ensure_ascii=False),
        "token_count": len(_tokenize(card["standard_answer"])),
    }

