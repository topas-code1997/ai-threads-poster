"""
note記事生成スクリプト
- Claude claude-sonnet-4-5で最新AIトレンド記事を生成
- ペルソナ「30代会社員・AI副業中」で人間味のある体験談入りの記事
- affiliate_links.json があれば、テーマに合うA8アフィリエイトリンクを自然に挿入
- 生成結果を note_article_YYYY-MM-DD_N.md として保存
"""
import os
import json
import random
import datetime
import hashlib
import anthropic

ARTICLE_TOPICS = [
    ("ChatGPT 使い方 最新 2026", "ChatGPT完全ガイド", "AI"),
    ("Claude AI 活用 副業 2026", "Claude AIで副業", "副業"),
    ("画像生成AI Midjourney Stable Diffusion 2026", "画像生成AI比較", "AI"),
    ("AI 自動化 業務効率化 2026", "AIで業務効率化", "業務効率化"),
    ("プロンプトエンジニアリング 稼ぐ 2026", "プロンプトで稼ぐ方法", "副業"),
    ("生成AI ビジネス活用事例 2026", "生成AIビジネス活用", "業務効率化"),
    ("AI エージェント 仕事 変化 2026", "AIエージェントが変える仕事", "AI"),
    ("Google Gemini 使い方 比較 2026", "Gemini徹底解説", "AI"),
    ("AI 音楽生成 Suno Udio 2026", "AI音楽生成ツール比較", "AI"),
    ("RAG 仕組み 活用 企業 2026", "RAGとは何か", "プログラミング"),
]

# 失敗談の方向性（記事ごとにランダムで1つ採用）
FAILURE_THEMES = [
    "ツール選びの失敗（最初に使ったツールが合わなくて他のに乗り換えた話）",
    "プロンプト試行錯誤（最初うまく出力されなくて、書き方を変えたら劇的に変わった話）",
    "業務効率化の苦労（自動化に時間をかけすぎて結局シンプルにした話）",
]

PERSONA = """あなたは「ai_life007」というハンドルネームでnoteを書いている、30代の会社員（事務職）です。
2024年から副業でAI活用を始め、今はChatGPT・Claude・画像生成AIを日常的に使っています。
専門家ではなく「ちょっと先を行く同僚」目線で、自分の経験を語ってください。"""

STYLE_RULES = """【文体ルール】
- 一人称「私は」「実際にやってみたら〜」を多用する
- 教科書的な網羅説明や箇条書きの羅列を避ける（見出しと箇条書きだけの構成は禁止）
- 「ぶっちゃけ」「正直」「実は」など感情表現を時折挟む
- 「〜と言われています」より「〜って感じでした」「〜だったんですよ」の口語混在
- 完璧主義より試行錯誤の生々しさを優先
- 段落を多めにして、地の文（散文）を中心に展開する

【NG表現】
- 「〜について解説します」「いかがでしたでしょうか」「ぜひ参考にしてください」
- 全体が ## 見出し+箇条書きだけの構成
- AI が書きました感のする丁寧すぎる定型文
- 「皆さん」「ご紹介します」のような距離のある書き方"""


def pick_article_topic(offset: int = 0) -> tuple[str, str, str]:
    today = datetime.date.today()
    idx = (int(hashlib.md5(str(today).encode()).hexdigest(), 16) + offset) % len(ARTICLE_TOPICS)
    return ARTICLE_TOPICS[idx]


def pick_affiliate_link(category: str) -> dict | None:
    """affiliate_links.json からカテゴリに合うリンクを1つランダムに選ぶ"""
    json_path = os.path.join(os.path.dirname(__file__), "affiliate_links.json")
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"affiliate_links.json読み込み失敗: {e}")
        return None

    # 一致するカテゴリを優先、なければ全カテゴリから
    candidates = list(data.get(category, []))
    if not candidates:
        for v in data.values():
            if isinstance(v, list):
                candidates.extend(v)
    if not candidates:
        return None
    return random.choice(candidates)


def generate_note_article(offset: int = 0) -> str:
    client = anthropic.Anthropic()

    query, theme, category = pick_article_topic(offset)
    today_str = datetime.date.today().strftime("%Y年%m月%d日")
    year = datetime.date.today().year
    failure_theme = random.choice(FAILURE_THEMES)

    print(f"検索クエリ: {query}")
    print(f"記事テーマ: {theme}")
    print(f"カテゴリ: {category}")
    print(f"失敗談テーマ: {failure_theme}")

    # アフィリリンクを取得
    affiliate = pick_affiliate_link(category)
    affiliate_block = ""
    disclosure_block = ""
    if affiliate:
        print(f"アフィリリンク: {affiliate.get('name', '名前不明')}")
        link_name = affiliate.get("name", "")
        link_url = affiliate.get("url", "")
        link_desc = affiliate.get("description", "")
        affiliate_block = f"""
【紹介ツール（必ず記事中に自然に組み込むこと）】
- ツール名: {link_name}
- リンクURL: {link_url}
- 補足: {link_desc}

紹介ルール：
1. 「私が実際に使ってみたツール」として体験ベースで紹介する
2. 記事中盤に「最近よかったツール」的な文脈で1回紹介する
3. まとめの直前にもう1回「気になる方はこちらから試してみてください」と置く
4. 上の2箇所では実際のリンクURLをそのままMarkdown形式で貼る
   例: [{link_name}はこちら]({link_url})
5. 売り込み色を出さず、「自分はこう使ってる」という共有の温度感で
"""
        disclosure_block = """
【ステマ規制対応・絶対遵守】
記事の最初の行（タイトル直後）に、必ず以下の一文をそのまま入れる：
> ※本記事はアフィリエイト広告を含みます
"""

    prompt = f"""{PERSONA}

{today_str}時点の情報をもとに、noteに投稿する日本語のSEO記事を書いてください。

{STYLE_RULES}

【記事要件】
- タイトル：「{year}年最新版」を含めつつ、ペルソナの一人称で語っているように見える自然な日本語に
- キーワード：{query}（自然に本文中に含める）
- 文字数：2000〜3000文字
- 対象読者：AIに興味を持ち始めた、自分と同じくらいの会社員
- 構成：自分の体験から入る → 最近の動向 → 自分の使い方 → まとめ
- 見出しはMarkdown（## / ###）で記述するが、見出し直下は必ず散文を入れる
- SEOキーワードを自然に含める（不自然な詰め込み禁止）
- 記事本文のみを出力し、前置きや説明は不要

【今回の必須要素】
1. 失敗談を1つ：{failure_theme}
   → これを記事中に自分のエピソードとして自然に盛り込む
2. 具体的な数字を最低1つ（例：「副業1ヶ月目は3000円だった」「30分かかってた作業が5分に」「3週間試した結果」など）
3. 個人的な感想を最低2つ（「これは本当に変わった」「最初は半信半疑だった」など）
{affiliate_block}{disclosure_block}
"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = next(
        (block.text for block in response.content if block.type == "text"), ""
    )
    article = text.strip()

    # ステマ表記の保険：アフィリリンクがあるのに開示文がなければ自動で先頭に挿入
    if affiliate and "アフィリエイト" not in article:
        lines = article.splitlines()
        if lines and lines[0].startswith("#"):
            # タイトル行の直後に挿入
            article = (
                lines[0]
                + "\n\n> ※本記事はアフィリエイト広告を含みます\n\n"
                + "\n".join(lines[1:])
            )
        else:
            article = "> ※本記事はアフィリエイト広告を含みます\n\n" + article

    return article


def save_article(content: str, num: int = 1) -> str:
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    filename = f"note_article_{today_str}_{num}.md"
    output_path = os.path.join(os.path.dirname(__file__), filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


def main():
    print("note記事を3本生成中...")
    for i in range(3):
        print(f"\n--- 記事 {i+1}/3 を生成中 ---")
        article = generate_note_article(offset=i)
        print(f"生成された記事（{len(article)}文字）:\n")
        print(article[:500] + "...\n")
        filepath = save_article(article, i+1)
        print(f"記事を保存しました: {filepath}")
    print("\n全3本の記事生成が完了しました！")


if __name__ == "__main__":
    main()
