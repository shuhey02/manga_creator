"""
LLM Service: Claude API を使ってストーリーからネームを生成する
"""
import json
import re
from typing import Optional
import anthropic
from pydantic import ValidationError

from ..config import settings
from ..models.schemas import Storyboard


# ─── JSON スキーマテンプレート ────────────────────────────────────────────────

STORYBOARD_SCHEMA = """
{
  "title": "string（作品タイトル）",
  "genre": "string（ジャンル）",
  "style": "string（スタイル）",
  "characters": [
    {
      "name": "string（キャラクター名）",
      "description": "string（日本語で外見・性格描写）",
      "prompt_keywords": "string（画像生成用英語キーワード、カンマ区切り）"
    }
  ],
  "pages": [
    {
      "page_number": 1,
      "page_notes": "string（ページ全体の演出メモ）",
      "panels": [
        {
          "panel_number": 1,
          "layout": {"x": 0, "y": 0, "width": 100, "height": 40},
          "composition": "string（構図説明）",
          "camera_angle": "string（俯瞰/アオリ/正面/斜め/クローズアップ等）",
          "background": "string（背景の詳細説明）",
          "characters": ["string（登場キャラ名リスト）"],
          "expression": "string（表情・ポーズ説明）",
          "dialogue": "string（セリフ、なければ空文字）",
          "sound_effect": "string（効果音・擬音語、なければ空文字）",
          "image_prompt_en": "string（英語画像生成プロンプト、Stable Diffusion向け）",
          "image_prompt_ja": "string（日本語画像生成プロンプト）",
          "speech_bubbles": [
            {
              "text": "string（吹き出し内テキスト）",
              "type": "normal",
              "orientation": "vertical",
              "position": {"x": 75, "y": 5, "width": 18, "height": 40}
            }
          ]
        }
      ]
    }
  ]
}
"""

SYSTEM_PROMPT = """あなたはプロの漫画ネーム作家・演出家です。
与えられたストーリーを、商業漫画のネームとして分解・構成してください。

## パネルレイアウトのルール（重要）
- layout の x, y, width, height は 0〜100 のパーセンテージで指定する
- 同一ページのパネルは重なってはいけない（合計が概ね100×100になるよう配置）
- 境界線のために各パネルは実際より数%小さく配置される（ガター分）
- 代表的なレイアウト例（これを参考に動的に設計する）:
  - 1コマ全面: [{"x":0,"y":0,"width":100,"height":100}]
  - 2コマ上下: [{"x":0,"y":0,"width":100,"height":50},{"x":0,"y":50,"width":100,"height":50}]
  - 3コマ（大＋2小）: [{"x":0,"y":0,"width":100,"height":35},{"x":0,"y":35,"width":60,"height":65},{"x":60,"y":35,"width":40,"height":65}]
  - 4コマ格子: [{"x":0,"y":0,"width":60,"height":50},{"x":60,"y":0,"width":40,"height":50},{"x":0,"y":50,"width":40,"height":50},{"x":40,"y":50,"width":60,"height":50}]
  - 5コマ（1大上＋4小下）: [{"x":0,"y":0,"width":100,"height":40},{"x":0,"y":40,"width":50,"height":30},{"x":50,"y":40,"width":50,"height":30},{"x":0,"y":70,"width":50,"height":30},{"x":50,"y":70,"width":50,"height":30}]

## 吹き出し配置のルール
- position はコマ内でのパーセンテージ（コマの左上を 0,0 とする）
- 吹き出しは絵の邪魔にならない位置（上部・隅・余白部分）に配置
- セリフは日本の漫画と同じ**縦書き**にする（orientation: "vertical"）。吹き出しは縦長にする
  （width 12〜22, height 25〜45 が目安。長いセリフは幅を広げて複数列にする）
- 縦書きの読み順に合わせ、同じコマに複数あるときは先に読む吹き出しを右・上に置く
- 英数字が中心の短い叫びなど、横書きが自然なものだけ orientation: "horizontal"（横長の吹き出し）にする

## 画像生成プロンプトのルール
- image_prompt_en は必ず英語で書く（Stable Diffusion / DALL-E / Midjourney向け）
- 各キャラクターの外見は characters の prompt_keywords を毎コマ必ず使用する
- アニメ・漫画スタイルを明記: "manga style, anime art, black and white, detailed lineart"
- カメラアングルと背景の詳細を必ず含める

## 出力形式
必ずJSON形式のみを出力してください。説明文やMarkdownコードブロックは不要です。"""


def _build_user_prompt(title: str, story: str, genre: str, style: str, num_pages: int) -> str:
    return f"""以下のストーリーを漫画ネームに変換してください。

## 作品情報
- タイトル: {title}
- ジャンル: {genre}
- スタイル: {style}
- ページ数: {num_pages}ページ

## ストーリー
{story}

## 出力JSONスキーマ
{STORYBOARD_SCHEMA}

上記のスキーマに従って、{num_pages}ページ分のネームをJSONで出力してください。
各ページに2〜6コマを配置し、ストーリーの流れが自然になるよう構成してください。
"""


def _extract_json(text: str) -> str:
    """LLM応答からJSONを抽出する（マークダウンコードブロック対応）"""
    # コードブロックを除去
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    # 最初の { から最後の } までを抽出
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return text


async def generate_storyboard(
    title: str,
    story: str,
    genre: str,
    style: str,
    num_pages: int,
) -> Storyboard:
    """Claude API を呼び出してネーム（storyboard）を生成する"""

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages = [
        {
            "role": "user",
            "content": _build_user_prompt(title, story, genre, style, num_pages),
        }
    ]

    # JSON が壊れていたら、エラー内容を添えて1回だけ直させる
    for attempt in range(2):
        message = await client.messages.create(
            model=settings.claude_model,
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        raw_text = message.content[0].text
        try:
            return Storyboard(**json.loads(_extract_json(raw_text)))
        except (json.JSONDecodeError, ValidationError) as e:
            if attempt == 1:
                raise ValueError(
                    f"LLMからの応答をネームとして解析できませんでした: {e}\n応答: {raw_text[:500]}"
                )
            messages += [
                {"role": "assistant", "content": raw_text},
                {
                    "role": "user",
                    "content": f"出力をスキーマ通りのJSONとして解析できませんでした: {e}\n"
                    "修正した完全なJSONだけを出力してください。",
                },
            ]
    raise AssertionError("unreachable")
