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
    "あなたは「ai_life007」というハンドルネームでSNS発信している、30代の会社員（事務職）です。\n"
    "2024年から副業でAI活用を始めて、ChatGPT・Claudeを日常的に使っています。\n"
    "専門家ではなく『ちょっと先を行く同僚』目線で、自分の体験ベースで投稿してください。\n\n"
    "Threadsに投稿する短文を日本語で書いてください。\n\n"
    "【要件】\n"
    "- 480文字以内（#PRハッシュタグ含めて500文字以内に収める）\n"
    "- 冒頭は『最近〜』『先週〜』『昨日〜』など時事性のある体験書き出し\n"
    "- 一人称『私』で、自分の実体験ベースで語る\n"
    "- 失敗談 or 気づき or 具体的な数字（『30分が5分に』など）を1つ含める\n"
    "- AIの最新動向を、自分が触ってみた感想として絡める\n"
    "- 教科書的な解説や箇条書きを避け、口語混じりの自然な文章で\n"
    "- 『ぶっちゃけ』『正直』『実は』などの感情表現を適度に\n"
    "- 末尾の絵文字は1〜3個\n"
    "- 絵文字の後に必ず改行して『👉 https://lit.link/ai-life007』を入れる\n"
    "- その後に必ず『#PR』を付ける（ステマ規制対応）\n"
    "- 投稿本文のみを出力。前置き・説明・マークダウンは不要\n\n"
    "【NG表現】\n"
    "- 『〜について解説します』『いかがでしたでしょうか』『皆さん』\n"
    "- AIが書いた感のする丁寧すぎる定型文\n"
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
    # params= だと日本語・改行がURLクエリに乗り400エラーになるため
    # data= でPOSTボディとして送信する
    data = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    response = requests.post(url, data=data)
    if not response.ok:
        print(f"Threads APIエラー: {response.status_code} {response.text}")
    response.raise_for_status()
    return response.json()["id"]


def publish_threads_post(creation_id: str) -> str:
    url = f"{THREADS_BASE_URL}/{THREADS_USER_ID}/threads_publish"
    data = {
        "creation_id": creation_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    response = requests.post(url, data=data)
    if not response.ok:
        print(f"Threads 公開APIエラー: {response.status_code} {response.text}")
    response.raise_for_status()
    return response.json()["id"]


def main():
    print("投稿文を生成中...")
    post_text = generate_post_with_web_search()

    # ステマ規制対応の保険：#PR が無ければ末尾に追加
    if "#PR" not in post_text and "#広告" not in post_text:
        # 500文字を超えないように調整
        suffix = "\n\n#PR"
        if len(post_text) + len(suffix) > 500:
            post_text = post_text[: 500 - len(suffix)] + suffix
        else:
            post_text = post_text + suffix

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
