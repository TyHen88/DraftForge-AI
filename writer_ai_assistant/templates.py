from __future__ import annotations

from dataclasses import dataclass

from writer_ai_assistant.prompt_builder import Mode


@dataclass(frozen=True)
class Template:
    key: str
    title: str
    mode: Mode
    instruction: str
    ask: str


TEMPLATES: dict[str, Template] = {
    "blog_post": Template(
        key="blog_post",
        title="Blog Post",
        mode=Mode.TEMPLATE,
        instruction="Write a blog post with: title, intro, sections with headings, and a conclusion. Use clear structure.",
        ask="Send: topic + target audience + key points (bullets).",
    ),
    "product_description": Template(
        key="product_description",
        title="Product Description",
        mode=Mode.TEMPLATE,
        instruction="Write a product description with: short headline, benefits, features, and a call-to-action.",
        ask="Send: product name + who it's for + top 3-5 benefits + key features.",
    ),
    "email_reply_template": Template(
        key="email_reply_template",
        title="Email Reply",
        mode=Mode.TEMPLATE,
        instruction="Write a professional email reply. Keep it concise, clear, and actionable.",
        ask="Send: the email you received (or summary) + what you want to reply.",
    ),
    "social_caption": Template(
        key="social_caption",
        title="Social Caption",
        mode=Mode.TEMPLATE,
        instruction="Write 5 social media captions (short), with 5 hashtag suggestions.",
        ask="Send: product/topic + platform + desired vibe + key message.",
    ),
}


def get_template(key: str) -> Template | None:
    return TEMPLATES.get(key)
