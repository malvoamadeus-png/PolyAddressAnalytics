#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polymarket 钱包指标计算脚本 (完全独立版本)

直接调用 Polymarket API 获取数据并计算 8 个核心指标：
- ROI (投资回报率)
- Sharpe Ratio (夏普比率)
- Profit Factor (获利因子)
- Max Drawdown (最大回撤)
- Win Rate (胜率)
- Position Size CV (仓位规模变异系数)
- HHI (市场集中度指数)
- Current Position Value (当前持仓价值)

输出格式：JSON

此版本完全独立，无需依赖项目根目录的任何文件。
"""

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests


# ============================================================================
# API 常量和速率限制
# ============================================================================

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
USER_PNL_API = "https://user-pnl-api.polymarket.com"


class _RateLimiter:
    def __init__(self, qps: float):
        self.qps = float(qps)
        self._next_ts = 0.0

    def acquire(self) -> None:
        if self.qps <= 0:
            return
        now = time.monotonic()
        wait_s = self._next_ts - now
        if wait_s > 0:
            time.sleep(wait_s)
            now = time.monotonic()
        step = 1.0 / self.qps
        self._next_ts = max(self._next_ts, now) + step


_LIMITERS: Dict[str, _RateLimiter] = {
    "gamma": _RateLimiter(20.0),
    "data": _RateLimiter(15.0),
    "clob": _RateLimiter(30.0),
    "user_pnl": _RateLimiter(8.0),
}

_PROGRESS = False


def _progress(msg: str) -> None:
    if not _PROGRESS:
        return
    try:
        sys.stderr.write(str(msg).rstrip() + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def _limit_for_url(url: str) -> Optional[_RateLimiter]:
    if url.startswith(GAMMA_API):
        return _LIMITERS["gamma"]
    if url.startswith(DATA_API):
        return _LIMITERS["data"]
    if url.startswith(CLOB_API):
        return _LIMITERS["clob"]
    if url.startswith(USER_PNL_API):
        return _LIMITERS["user_pnl"]
    return None


# ============================================================================
# HTTP 工具函数
# ============================================================================

def _sleep_backoff(attempt: int, base_s: float) -> None:
    time.sleep(base_s * (2**attempt))


def http_get_json(
    session: requests.Session,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    timeout_s: float = 25.0,
    max_retries: int = 3,
) -> Any:
    last_err: Optional[BaseException] = None
    for attempt in range(max_retries):
        try:
            lim = _limit_for_url(url)
            if lim is not None:
                lim.acquire()
            r = session.get(url, params=params, timeout=timeout_s, headers={"accept": "application/json"})
            if r.status_code in (429, 500, 502, 503, 504):
                _sleep_backoff(attempt, 1.0)
                continue
            if 400 <= r.status_code < 500:
                raise requests.HTTPError(f"{r.status_code} {r.text[:500]}", response=r)
            r.raise_for_status()
            return r.json()
        except BaseException as e:
            last_err = e
            if isinstance(e, requests.HTTPError) and e.response is not None:
                code = e.response.status_code
                if code in (400, 401, 403, 404):
                    raise
            _sleep_backoff(attempt, 1.0)
    raise RuntimeError(f"GET {url} failed after retries: {last_err}")


# ============================================================================
# 数据获取函数
# ============================================================================

def fetch_user_pnl_series(
    session: requests.Session, address: str, interval: str = "all", fidelity: str = "12h"
) -> List[Tuple[str, float]]:
    data = http_get_json(
        session,
        f"{USER_PNL_API}/user-pnl",
        params={"user_address": address, "interval": interval, "fidelity": fidelity},
        timeout_s=20.0,
        max_retries=3,
    )
    if not isinstance(data, list):
        return []
    out: List[Tuple[str, float]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        t = row.get("t")
        p = row.get("p")
        if not isinstance(t, (int, float)) or not isinstance(p, (int, float)):
            continue
        dt = datetime.fromtimestamp(float(t), tz=timezone.utc)
        out.append((dt.isoformat(), float(p)))
    return out


def fetch_positions(session: requests.Session, address: str) -> List[Dict[str, Any]]:
    url = f"{DATA_API}/positions"
    limit = 500
    offset = 0
    out: List[Dict[str, Any]] = []
    while True:
        _progress(f"    ↳ positions page offset={offset}")
        data = http_get_json(session, url, params={"user": address, "sizeThreshold": 0, "limit": limit, "offset": offset})
        if not isinstance(data, list) or not data:
            break
        for row in data:
            if isinstance(row, dict):
                out.append(row)
        if len(data) < limit:
            break
        offset += limit
    return out


def fetch_closed_positions(session: requests.Session, address: str) -> List[Dict[str, Any]]:
    url = f"{DATA_API}/closed-positions"
    limit = 50
    offset = 0
    out: List[Dict[str, Any]] = []
    while True:
        _progress(f"    ↳ closed-positions page offset={offset}")
        data = http_get_json(session, url, params={"user": address, "limit": limit, "offset": offset})
        if not isinstance(data, list) or not data:
            break
        for row in data:
            if isinstance(row, dict):
                out.append(row)
        if len(data) < limit:
            break
        offset += limit
    return out


# ============================================================================
# 数据解析函数
# ============================================================================

def _as_float(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except Exception:
            return None
    return None


def extract_position_fields(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    token_id = row.get("asset") or row.get("asset_id") or row.get("tokenId") or row.get("token_id")
    market = row.get("market") or row.get("conditionId") or row.get("condition_id")
    slug = row.get("eventSlug") or row.get("slug") or row.get("market_slug")
    outcome = row.get("outcome") or row.get("title") or row.get("name")

    size = None
    for k in ("size", "shares", "balance", "quantity", "qty"):
        size = _as_float(row.get(k))
        if size is not None:
            break

    total_bought = _as_float(row.get("totalBought") or row.get("total_bought"))
    initial_value = _as_float(row.get("initialValue") or row.get("initial_value"))
    current_value = _as_float(row.get("currentValue") or row.get("current_value"))
    avg_price = _as_float(row.get("avgPrice") or row.get("avg_price"))

    cost_basis = None
    for k in ("initialValue", "initial_value", "costBasis", "cost_basis", "avgCost", "avg_cost", "cost"):
        cost_basis = _as_float(row.get(k))
        if cost_basis is not None:
            break
    if cost_basis is None:
        if avg_price is not None and size is not None:
            cost_basis = abs(size) * avg_price

    cash_pnl = None
    for k in ("cashPnl", "cash_pnl", "pnl", "profit"):
        cash_pnl = _as_float(row.get(k))
        if cash_pnl is not None:
            break

    realized_pnl = _as_float(row.get("realizedPnl") or row.get("realized_pnl"))
    cur_price = _as_float(row.get("curPrice") or row.get("cur_price"))
    closed = bool(row.get("redeemed") or row.get("closed") or (row.get("redeemable") is True and row.get("size") in (0, "0", 0.0)))

    return {
        "market": str(market) if market else None,
        "slug": str(slug) if slug else None,
        "token_id": str(token_id) if token_id else None,
        "outcome": str(outcome) if isinstance(outcome, str) else None,
        "size": size,
        "total_bought": total_bought,
        "initial_value": initial_value,
        "current_value": current_value,
        "avg_price": avg_price,
        "cost_basis": cost_basis,
        "cash_pnl": cash_pnl,
        "realized_pnl": realized_pnl,
        "cur_price": cur_price,
        "closed": closed,
        "raw": row,
    }


# ============================================================================
# 统计工具函数
# ============================================================================

def mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def std(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    v = sum((x - m) ** 2 for x in xs) / len(xs)
    return math.sqrt(v)


# ============================================================================
# 指标计算函数
# ============================================================================

def compute_pnl_drawdown_sharpe(
    pnl_series: List[Tuple[str, float]], annualization_periods: float = 365.0
) -> Tuple[Optional[float], Optional[float]]:
    if len(pnl_series) < 3:
        return None, None
    vals = [v for _, v in pnl_series]
    peak = None
    max_dd = 0.0
    for v in vals:
        if peak is None or v > peak:
            peak = v
        if peak is None:
            continue
        dd = float(peak) - float(v)
        if dd > max_dd:
            max_dd = dd
    changes = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
    s = std(changes)
    sharpe = None
    if s > 0:
        sharpe = (mean(changes) / s) * math.sqrt(float(annualization_periods))
    return max_dd if max_dd > 0 else 0.0, sharpe


def compute_metrics_snapshot(
    positions: List[Dict[str, Any]],
    max_drawdown: Optional[float],
    sharpe: Optional[float],
) -> Tuple[Dict[str, Any], str]:
    per_market_pnl = {}
    realized = 0.0
    total_raw = 0.0

    for p in positions:
        mkey = p.get("market") or p.get("slug") or "unknown"
        realized_field = p.get("realized_pnl")
        if isinstance(realized_field, (int, float)):
            realized += float(realized_field)
        cash_pnl = p.get("cash_pnl")
        if isinstance(cash_pnl, (int, float)):
            pnl = float(cash_pnl)
            total_raw += pnl
            per_market_pnl[mkey] = per_market_pnl.get(mkey, 0.0) + pnl

    total_by_market = sum(per_market_pnl.values())
    unrealized = total_by_market - realized
    gp = sum(v for v in per_market_pnl.values() if v > 0)
    gl = sum(-v for v in per_market_pnl.values() if v < 0)
    pf = None
    if gl > 0:
        pf = gp / gl

    cost_basis_total = 0.0
    cost_basis_known = False
    for p in positions:
        tb = p.get("total_bought")
        if isinstance(tb, (int, float)) and tb > 0:
            cost_basis_total += float(tb)
            cost_basis_known = True
    roi = None
    if cost_basis_known and cost_basis_total > 0:
        roi = total_by_market / cost_basis_total

    details = {
        "rawPositionsCashPnLSum": total_raw,
        "rawPositionsCashPnLSumByMarket": total_by_market,
    }

    confidence = "high"
    if not per_market_pnl:
        confidence = "low"
    elif not cost_basis_known:
        confidence = "medium"

    return (
        {
            "total_pnl": total_by_market,
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "profit_factor": pf,
            "roi": roi,
            "max_drawdown": max_drawdown,
            "sharpe": sharpe,
            "details": details,
        },
        confidence,
    )


def compute_position_based_stats(
    positions: List[Dict[str, Any]], positions_raw_count: int, closed_positions_raw_count: int
) -> Dict[str, Any]:
    total_trades = int(positions_raw_count) + int(closed_positions_raw_count)
    winning = 0
    losing = 0
    considered = 0

    w_sum = 0.0
    wx_sum = 0.0

    for p in positions:
        cash_pnl = p.get("cash_pnl")
        if isinstance(cash_pnl, (int, float)):
            considered += 1
            if float(cash_pnl) > 0:
                winning += 1
            elif float(cash_pnl) < 0:
                losing += 1

        avg_price = p.get("avg_price")
        total_bought = p.get("total_bought")
        if isinstance(avg_price, (int, float)) and isinstance(total_bought, (int, float)) and float(total_bought) > 0:
            w = float(total_bought)
            w_sum += w
            wx_sum += float(avg_price) * w

    win_rate = None
    if considered > 0:
        win_rate = winning / float(considered)
    avg_trade_price = None
    if w_sum > 0:
        avg_trade_price = wx_sum / w_sum

    return {
        "current_position_value_usd": None,
        "total_trades": total_trades,
        "winning_trades": winning,
        "losing_trades": losing,
        "win_rate": win_rate,
        "avg_trade_price": avg_trade_price,
    }


def compute_position_size_cv(positions: List[Dict[str, Any]]) -> Optional[float]:
    """计算仓位规模变异系数 (Coefficient of Variation)"""
    buy_amounts = []
    for p in positions:
        tb = p.get("total_bought")
        if isinstance(tb, (int, float)) and tb > 0:
            buy_amounts.append(float(tb))

    if len(buy_amounts) < 2:
        return None

    m = mean(buy_amounts)
    if m == 0:
        return None

    s = std(buy_amounts)
    return s / m


def compute_hhi(positions: List[Dict[str, Any]]) -> Optional[float]:
    """计算市场集中度指数 (Herfindahl-Hirschman Index)"""
    market_exposure = {}
    total_exposure = 0.0

    for p in positions:
        market = p.get("market") or p.get("slug") or "unknown"
        tb = p.get("total_bought")
        if isinstance(tb, (int, float)) and tb > 0:
            exposure = float(tb)
            market_exposure[market] = market_exposure.get(market, 0.0) + exposure
            total_exposure += exposure

    if total_exposure == 0 or len(market_exposure) == 0:
        return None

    hhi = 0.0
    for exposure in market_exposure.values():
        share = exposure / total_exposure
        hhi += share * share

    return hhi


# ============================================================================
# 主函数
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="计算 Polymarket 钱包指标")
    parser.add_argument("--address", required=True, help="钱包地址")
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    args = parser.parse_args()

    address = args.address.lower().strip()

    global _PROGRESS
    _PROGRESS = True

    print(f"正在获取钱包数据: {address}", file=sys.stderr)

    session = requests.Session()

    try:
        # 1. 获取持仓数据
        print("正在获取持仓数据...", file=sys.stderr)
        positions_raw = fetch_positions(session, address)
        closed_positions_raw = fetch_closed_positions(session, address)

        if not positions_raw and not closed_positions_raw:
            result = {
                "address": address,
                "snapshot_date": datetime.now(timezone.utc).isoformat(),
                "metrics": {},
                "summary": {},
                "data_quality": {
                    "trades_analyzed": 0,
                    "date_range": None,
                    "warning": "未找到交易历史"
                }
            }
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print("警告: 未找到交易历史", file=sys.stderr)
            return

        # 2. 解析持仓数据
        print("正在解析持仓数据...", file=sys.stderr)
        all_positions_raw = positions_raw + closed_positions_raw
        positions = []
        for raw in all_positions_raw:
            parsed = extract_position_fields(raw)
            if parsed:
                positions.append(parsed)

        # 3. 获取 PnL 时间序列
        print("正在获取 PnL 时间序列...", file=sys.stderr)
        pnl_series = fetch_user_pnl_series(session, address)

        # 4. 计算 Max Drawdown 和 Sharpe Ratio
        max_drawdown, sharpe = compute_pnl_drawdown_sharpe(pnl_series)

        # 5. 计算核心指标
        print("正在计算指标...", file=sys.stderr)
        metrics_data, confidence = compute_metrics_snapshot(positions, max_drawdown, sharpe)

        # 6. 计算基于持仓的统计
        position_stats = compute_position_based_stats(positions, len(positions_raw), len(closed_positions_raw))

        # 7. 计算自定义指标
        position_size_cv = compute_position_size_cv(positions)
        hhi = compute_hhi(positions)

        # 8. 合并所有指标
        final_metrics = {
            "roi": metrics_data.get("roi"),
            "sharpe_ratio": metrics_data.get("sharpe"),
            "profit_factor": metrics_data.get("profit_factor"),
            "max_drawdown": metrics_data.get("max_drawdown"),
            "win_rate": position_stats.get("win_rate"),
            "position_size_cv": position_size_cv,
            "hhi": hhi,
            "current_position_value_usd": position_stats.get("current_position_value_usd")
        }

        summary = {
            "total_pnl": metrics_data.get("total_pnl"),
            "total_trades": position_stats.get("total_trades"),
            "winning_trades": position_stats.get("winning_trades"),
            "losing_trades": position_stats.get("losing_trades")
        }

        # 9. 数据质量信息
        total_trades = position_stats.get("total_trades", 0)
        warning = None
        if total_trades < 20:
            warning = f"交易数量较少 ({total_trades} 笔)，统计显著性可能不足"

        data_quality = {
            "trades_analyzed": total_trades,
            "date_range": None,
            "warning": warning,
            "confidence": confidence
        }

        # 10. 构建最终输出
        result = {
            "address": address,
            "snapshot_date": datetime.now(timezone.utc).isoformat(),
            "metrics": final_metrics,
            "summary": summary,
            "data_quality": data_quality
        }

        # 11. 写入输出文件
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"指标计算完成，已保存到 {args.output}", file=sys.stderr)

    except Exception as e:
        print(f"错误: {str(e)}", file=sys.stderr)
        result = {
            "address": address,
            "snapshot_date": datetime.now(timezone.utc).isoformat(),
            "metrics": {},
            "summary": {},
            "data_quality": {
                "trades_analyzed": 0,
                "date_range": None,
                "warning": f"数据获取失败: {str(e)}"
            }
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        raise


if __name__ == '__main__':
    main()
