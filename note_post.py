"""
note記事生成スクリプト
- Claude claude-sonnet-4-5で最新AIトレンド記事を生成
- SEO最適化された日本語記事を生成
- 生成結果を note_article_YYYY-MM-DD.md として保存
"""
import os
import datetime
import hashlib
import anthropic

ARTICLE_TOPICS = [
    ("ChatGPT 使い方 最新 2026", "ChatGPT完全ガイド"),
    ("Claude AI 活用 副業 2026", "Claude AIで副業"),
    ("画像生成AI Midjourney Stable Diffusion 2026", "画像生成AI比較"),
    ("AI 自動化 業務効率化 2026", "AIで業務効率化"),
    ("プロンプトエンジニアリング 稼ぐ 2026", "プロンプトで稼ぐ方法"),
    ("生成AI ビジネス活用事例 2026", "生成AIビジネス活用"),
    ("AI エージェント 仕事 変化 2026", "AIエージェントが変える仕事"),
    ("Google Gemini 使い方 比較 2026", "Gemini徹底解説"),
    ("AI 音楽生成 Suno Udio 2026", "AI音楽生成ツール比較"),
    ("RAG 仕組み 活用 企業 2026", "RAGとは何か"),
]

def pick_article_topic() -> tuple[str, str]:
    today = datetime.date.today()
    idx = int(hashlib.md5(str(today).encode()).hexdigest(), 16) % len(ARTICLE_TOPICS)
    return ARTICLE_TOPICS[idx]

def generate_note_article() -> str:
    client = anthropic.Anthropic()

    query, theme = pick_article_topic()
    today_str = datetime.date.today().strftime("%Y年%m月%d日")
    year = datetime.date.today().year

    print(f"検索クエリ: {query}")
    print(f"記事テーマ: {theme}")

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{today_str}時点の情報をもとに、noteに投稿するSEO最適化された日本語の解説記事を書いてください。\n\n"
                    f"【記事要件】\n"
                    f"- テーマ：{theme}\n"
                    f"- キーワード：{query}\n"
                    f"- タイトルに「{year}年最新版」を含める\n"
                    f"- 文字数：2000〜3000文字\n"
                    f"- 対象読者：AIに興味を持ち始めた初心者\n"
                    f"- 構成：導入 → 基本説明 → 最新トレンド → 具体的な活用法 → まとめ\n"
                    f"- 見出しはMarkdown（## / ###）で記述\n"
                    f"- SEOキーワードを自然に含める\n"
                    f"- 記事本文のみを出力し、前置きや説明は不要\n"
                ),
            }
        ],
    )

    text = next(
        (block.text for block in response.content if block.type == "text"), ""
    )
    return text.strip()

def save_article(content: str) -> str:
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    filename = f"note_article_{today_str}.md"
    output_path = os.path.join(os.path.dirname(__file__), filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path

def main():
    print("note記事を生成中...")
    article = generate_note_article()
    print(f"\n生成された記事（{len(article)}文字）:\n")
    print(article[:500] + "...\n")
    filepath = save_article(article)
    print(f"記事を保存しました: {filepath}")

if __name__ == "__main__":
    main()
