from app.services.kb_service import load_sections, split_page

PAGE = """# Fees

Intro to fees.

## Refunds

Refunds take 5 days.

```
# not a heading
```

## Empty

# Limits

Daily limit is 500.
"""


def test_split_page_by_heading_with_trail():
    sections = split_page("fees.md", PAGE)
    assert [(s.heading, s.text.splitlines()[0]) for s in sections] == [
        ("Fees", "Intro to fees."),
        ("Fees > Refunds", "Refunds take 5 days."),
        ("Limits", "Daily limit is 500."),
    ]
    assert "# not a heading" in sections[1].text
    assert sections[1].content.startswith("Fees > Refunds\nRefunds take 5 days.")


def test_load_sections_skips_hidden_folders(tmp_path):
    (tmp_path / "guide").mkdir()
    (tmp_path / "guide" / "cards.md").write_text("# Cards\n\nOrder a card.", encoding="utf-8")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "notes.md").write_text("# Hidden\n\nSkip me.", encoding="utf-8")

    sections = load_sections(tmp_path)

    assert [(s.page, s.heading) for s in sections] == [("guide/cards.md", "Cards")]
