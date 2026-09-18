"""SHIRURU・ノベルティ データ（スプレッドシート）の抽出・加工。

戻り値:
    bq_srr : BigQuery 出力用データフレーム
"""

import logging
import pandas as pd
from gspread_dataframe import get_as_dataframe

from . import config
from .store_mapping import store_dict

logger = logging.getLogger(__name__)


def _load_shiruru(ws):
    """SHIRURU配布実績_raw シートを読み込む（2行目ヘッダー）。"""
    # 2行目をヘッダーとして読み込み (header=1)
    df = get_as_dataframe(ws, header=1, evaluate_formulas=True)
    if df.empty:
        return pd.DataFrame()

    # 余計な改行やスペースをトリム
    df.columns = [str(c).strip() for c in df.columns]

    # 日時、店舗番号（または店舗名）が存在するレコードを抽出
    if "日時" not in df.columns:
        return pd.DataFrame()

    df = df[df["日時"].notnull() & (df["日時"].astype(str).str.strip() != "")].copy()

    # 店舗番号の補正
    if "店舗番号" in df.columns:
        df["store_code"] = pd.to_numeric(df["店舗番号"], errors="coerce").fillna(0).astype(int)
    elif "店舗名" in df.columns:
        df["store_code"] = df["店舗名"].map(store_dict).fillna(0).astype(int)
    else:
        df["store_code"] = 0

    df["date"] = pd.to_datetime(df["日時"], errors="coerce")
    df = df[df["date"].notnull() & (df["store_code"] > 0)].copy()

    df["dist_type"] = "shiruru"
    return df[["date", "store_code", "dist_type"]]


def _load_novelty(ws):
    """ノベルティ配布実績_raw シートを読み込む（2行目ヘッダー）。"""
    # 2行目をヘッダーとして読み込み (header=1)
    df = get_as_dataframe(ws, header=1, evaluate_formulas=True)
    if df.empty:
        return pd.DataFrame()

    # A〜F列のみを使用（横並びの重複列を除外するためインデックス指定）
    df = df.iloc[:, :6].copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "日時" not in df.columns:
        return pd.DataFrame()

    df = df[df["日時"].notnull() & (df["日時"].astype(str).str.strip() != "")].copy()

    # 店舗番号の補正
    if "店舗番号" in df.columns:
        df["store_code"] = pd.to_numeric(df["店舗番号"], errors="coerce").fillna(0).astype(int)
    elif "店舗名" in df.columns:
        df["store_code"] = df["店舗名"].map(store_dict).fillna(0).astype(int)
    else:
        df["store_code"] = 0

    df["date"] = pd.to_datetime(df["日時"], errors="coerce")
    df = df[df["date"].notnull() & (df["store_code"] > 0)].copy()

    df["dist_type"] = "novelty"
    return df[["date", "store_code", "dist_type"]]


def build(gc):
    """SHIRURU と ノベルティ データを構築して bq_srr を返す。"""
    ss_srr = gc.open_by_url(config.SHIRURU_SPREADSHEET_URL)

    # 1. SHIRURU配布実績_raw
    try:
        ws_shiruru = ss_srr.worksheet("SHIRURU配布実績_raw")
        df_srr = _load_shiruru(ws_shiruru)
    except Exception as e:
        logger.warning("SHIRURU配布実績_raw の読み込み失敗: %s", e)
        df_srr = pd.DataFrame(columns=["date", "store_code", "dist_type"])

    # 2. ノベルティ配布実績_raw
    try:
        ws_novelty = ss_srr.worksheet("ノベルティ配布実績_raw")
        df_novelty = _load_novelty(ws_novelty)
    except Exception as e:
        logger.warning("ノベルティ配布実績_raw の読み込み失敗: %s", e)
        df_novelty = pd.DataFrame(columns=["date", "store_code", "dist_type"])

    df_combined = pd.concat([df_srr, df_novelty], ignore_index=True)
    return df_combined