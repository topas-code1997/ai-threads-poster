import os
import time
import anthropic
import requests

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
THREADS_ACCESS_TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
THREADS_USER_ID = os.environ["THREADS_USER_ID"]

THREADS_BASE_URL = "https://graph.threads.net/v1.0"

TOPICS = [
    "生成AIの仕組み（大規模言語モデルとは何か）",
    "プロンプトエンジニアリングの基本テクニック",
    "ChatGPTとClaude、Geminiの違いと使い分け",
    "AIが画像を生成する仕組み（Stable Diffusionなど）",
    "機械学習と深層学習の違いをわかりやすく解説",
    "AIによる音楽・動画生成の最前線",
    "RAGとは何か？AIに最新情報を与える技術",
    "エージェントAIとは何か？自律的に動くAIの仕組み",
    "量子コンピュータがAIに与える影響",
    "AIと著作権・倫理の問題をやさしく解説",
    "ベクトルデータベースとは？AI検索の仕組み",
    "ファインチューニングとは？AIを専門家にする方法",
    "MCPとは何か？AIがツールを使う新しい仕組み",
    "マルチモーダルAIとは？テキスト以外を理解するAI",
    "AIのハルシネーション（幻覚）とその対策",
]

import datetime
import hashlib

def pick_topic():
    today = datetime.date.today()
    idx = int(hashlib.md5(str(today).encode()).hexdigest(), 16) % len(TOPICS)
    return TOPICS[idx]


def generate_post(topic: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Threadsに投稿する、AIやテクノロジーの初心者向け解説を日本語で書いてください。\n\n"
                    f"テーマ：{topic}\n\n"
                    f"要件：\n"
                    f"- 500文字以内\n"
                    f"- 読みやすく、わかりやすい言葉を使う\n"
                    f"- 最後に関連する絵文字を1〜3個つける\n"
                    f"- ハッシュタグは不要\n"
                    f"- 本文のみを出力し、前置き・説明・マークダウンは不要\n"
                ),
            }
        ],
    )

    text = next(
        (block.text for block in response.content if block.type == "text"), ""
    )
    return text.strip()


def create_threads_container(text: str) -> str:
    url = f"{THREADS_BASE_URL}/{THREADS_USER_ID}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    response = requests.post(url, params=params)
    response.raise_for_status()
    data = response.json()
    return data["id"]


def publish_threads_post(creation_id: str) -> str:
    url = f"{THREADS_BASE_URL}/{THREADS_USER_ID}/threads_publish"
    params = {
        "creation_id": creation_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    response = requests.post(url, params=params)
    response.raise_for_status()
    data = response.json()
    return data["id"]


def main():
    print("投稿テーマを選択中...")
    topic = pick_topic()
    print(f"テーマ: {topic}")

    print("投稿文を生成中...")
    post_text = generate_post(topic)
    print(f"生成された投稿文（{len(post_text)}文字）:\n{post_text}\n")

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
