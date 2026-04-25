import os
import time
import datetime
import hashlib
import anthropic
import requests

THREADS_ACCESS_TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
THREADS_USER_ID = os.environ["THREADS_USER_ID"]

THREADS_BASE_URL = "https://graph.threads.net/v1.0"

SEARCH_QUERIES = [
    "AI 最新ニュース 2026",
    "ChatGPT 新機能 最新情報",
    "Claude AI 最新アップデート",
    "生成AI ビジネス活用 トレンド",
    "AI 副業 稼ぎ方 最新",
    "画像生成AI 最新モデル",
    "AI エージェント 最新動向",
    "Google Gemini 最新情報",
    "AI 音楽生成 最新ツール",
    "プロンプトエンジニアリング 最新テクニック",
    "RAG LLM 最新技術",
    "MCP AI ツール連携 最新",
    "マルチモーダルAI 最新モデル",
    "AI 規制 倫理 最新ニュース",
    "ファインチューニング 最新手法",
]

PROMPT_TEMPLATE = (
    "Threadsに投稿する初心者向けのAI解説を日本語で書いてください。\n\n"
    "要件：\n"
    "- 500文字以内\n"
    "- 時事性のある書き出し\n"
    "- AIの最新動向を1つ取り上げ、初心者にわかりやすく解説\n"
    "- 最後に関連する絵文字を1〜3個つける\n"
    "- ハッシュタグは不要\n"
    "- 投稿本文のみを出力し、前置き・説明・マークダウンは不要\n"
)


def pick_search_query() -> str:
    today = datetime.date.today()
    idx = int(hashlib.md5(str(today).encode()).hexdigest(), 16) % len(SEARCH_QUERIES)
    return SEARCH_QUERIES[idx]


def generate_post_without_search() -> str:
    """web検索なしで投稿文を生成（フォールバック用）"""
    client = anthropic.Anthropic()
    query = pick_search_query()
    print("web検索なしで生成中...")

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    f"「{query}」をテーマに、" + PROMPT_TEMPLATE
                ),
            }
        ],
    )
    text = next(
        (block.text for block in response.content if block.type == "text"), ""
    )
    return text.strip()


def generate_post_with_web_search() -> str:
    """web検索ありで投稿文を生成（最大3回リトライ、失敗時はフォールバック）"""
    client = anthropic.Anthropic()
    query = pick_search_query()
    print(f"検索クエリ: {query}")

    for attempt in range(3):
        try:
            print(f"web検索試行 {attempt + 1}/3...")
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"「{query}」で検索して最新情報を収集してください。"
                            f"その内容をもとに、" + PROMPT_TEMPLATE
                        ),
                    }
                ],
            )
            text = next(
                (block.text for block in response.content if block.type == "text"), ""
            )
            if len(text) > 400:
                print(f"web検索成功（{len(text)}文字）")
                return text.strip()
            else:
                print(f"試行{attempt + 1}回目：文字数不足（{len(text)}文字）、リトライします...")

        except Exception as e:
            print(f"試行{attempt + 1}回目失敗: {e}")

        if attempt < 2:
            time.sleep(5)

    # 3回全部失敗したらweb検索なしにフォールバック
    print("web検索3回失敗。web検索なしに切り替えます...")
    return generate_post_without_search()


def create_threads_container(text: str) -> str:
    url = f"{THREADS_BASE_URL}/{THREADS_USER_ID}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()["id"]


def publish_threads_post(creation_id: str) -> str:
    url = f"{THREADS_BASE_URL}/{THREADS_USER_ID}/threads_publish"
    params = {
        "creation_id": creation_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()["id"]


def main():
    print("投稿文を生成中...")
    post_text = generate_post_with_web_search()
    print(f"\n生成された投稿文（{len(post_text)}文字）:\n{post_text}\n")

    print("Threadsコンテナを作成中...")
    creation_id = create_threads_container(post_text)
    print(f"コンテナID: {creation_id}")

    print("公開待機中（30秒）...")
    time.sleep(30)

    print("投稿を公開中...")
    post_id = publish_threads_post(creation_id)
    print(f"投稿完了！投稿ID: {post_id}")


if __name__ == "__main__":
    main()
