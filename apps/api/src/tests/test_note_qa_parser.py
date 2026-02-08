from src.ingest.note_qa_parser import parse_note_to_qa_cards


def test_parse_note_to_qa_cards_basic():
    text = """
## 5.1 语言基础与语法

### 1）Integer 和 int 的区别？
- int 是基本类型
- Integer 是包装类型

### 2）JRE 和 JDK 的区别？
- JRE 用于运行
- JDK 用于开发
"""
    cards = parse_note_to_qa_cards(text, source_id="note_demo")
    assert len(cards) == 2
    assert cards[0]["question"].startswith("Integer 和 int")
    assert cards[0]["topic"] == "java_basic"
    assert len(cards[0]["key_points"]) >= 2
    assert cards[0]["question_id"].startswith("qa_note_demo_")


def test_parse_note_to_qa_cards_dedup_by_question():
    text = """
## 主题
### 1）什么是 HashMap？
- 哈希表

### 2）什么是 HashMap？
- 数组 + 链表
"""
    cards = parse_note_to_qa_cards(text, source_id="note_dup")
    assert len(cards) == 1

