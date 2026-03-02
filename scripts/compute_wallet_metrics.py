#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polymarket 钱包指标计算脚本

调用根目录的 polymarket_metrics.py 获取数据并计算 8 个核心指标：
- ROI (投资回报率)
- Sharpe Ratio (夏普比率)
- Profit Factor (获利因子)
- Max Drawdown (最大回撤)
- Win Rate (胜率)
- Position Size CV (仓位规模变异系数)
- HHI (市场集中度指数)
- Current Position Value (当前持仓价值)

输出格式：JSON
"""

import sys
import os
import argparse
import json
import subprocess
import tempfile
import sqlite3
from datetime import datetime, timezone


def get_root_dir():
    """获取项目根目录"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # scripts -> wallet-metrics -> skills -> .trae -> root
    return os.path.abspath(os.path.join(script_dir, '../../../..'))


def run_polymarket_metrics(address, db_path):
    """
    调用根目录的 polymarket_metrics.py 脚本

    返回: (success: bool, error_msg: str)
    """
    root_dir = get_root_dir()
    script_path = os.path.join(root_dir, 'polymarket_metrics.py')

    if not os.path.exists(script_path):
        return False, f"未找到 polymarket_metrics.py: {script_path}"

    cmd = [
        sys.executable,
        script_path,
        '--address', address,
        '--db', db_path,
        '--progress'
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=root_dir,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            return False, f"脚本执行失败: {result.stderr}"

        return True, None

    except subprocess.TimeoutExpired:
        return False, "脚本执行超时 (120秒)"
    except Exception as e:
        return False, f"执行错误: {str(e)}"


def read_metrics_from_db(db_path, address):
    """
    从 SQLite 数据库读取指标

    返回: dict 或 None
    """
    if not os.path.exists(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM address_metrics
            WHERE address = ?
            ORDER BY snapshot_utc DESC
            LIMIT 1
        """, (address,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        # 转换为字典
        data = dict(row)

        # 解析 details_json
        if data.get('details_json'):
            try:
                data['details'] = json.loads(data['details_json'])
            except:
                data['details'] = {}
        else:
            data['details'] = {}

        return data

    except Exception as e:
        print(f"读取数据库错误: {e}", file=sys.stderr)
        return None


def extract_metrics(db_data):
    """
    从数据库数据中提取 8 个核心指标

    返回: dict
    """
    if not db_data:
        return {
            "metrics": {},
            "summary": {},
            "data_quality": {
                "trades_analyzed": 0,
                "date_range": None,
                "warning": "未找到交易历史"
            }
        }

    details = db_data.get('details', {})

    # 提取指标
    metrics = {
        "roi": db_data.get('roi'),
        "sharpe_ratio": db_data.get('sharpe'),
        "profit_factor": db_data.get('profit_factor'),
        "max_drawdown": db_data.get('max_drawdown'),
        "win_rate": db_data.get('win_rate'),
        "position_size_cv": db_data.get('position_size_cv'),
        "hhi": db_data.get('hhi'),
        "current_position_value_usd": db_data.get('current_position_value_usd')
    }

    # 提取汇总信息
    total_trades = db_data.get('total_trades', 0)
    winning_trades = db_data.get('winning_trades', 0)
    losing_trades = db_data.get('losing_trades', 0)

    summary = {
        "total_pnl": db_data.get('total_pnl'),
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades
    }

    # 数据质量信息
    warning = None
    if total_trades < 20:
        warning = f"交易数量较少 ({total_trades} 笔)，统计显著性可能不足"

    date_range = None
    if details.get('FirstTradeDate') and details.get('LastTradeDate'):
        date_range = f"{details['FirstTradeDate']} to {details['LastTradeDate']}"

    data_quality = {
        "trades_analyzed": total_trades,
        "date_range": date_range,
        "warning": warning
    }

    return {
        "metrics": metrics,
        "summary": summary,
        "data_quality": data_quality
    }


def main():
    parser = argparse.ArgumentParser(description='计算 Polymarket 钱包的核心交易指标')
    parser.add_argument('--address', required=True, help='钱包地址 (0x...)')
    parser.add_argument('--output', required=True, help='输出 JSON 文件路径')

    args = parser.parse_args()

    address = args.address.strip()

    # 创建临时数据库
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sqlite', delete=False) as tmp:
        tmp_db_path = tmp.name

    try:
        # 1. 运行 polymarket_metrics.py
        print(f"正在获取钱包 {address} 的数据...", file=sys.stderr)
        success, error = run_polymarket_metrics(address, tmp_db_path)

        if not success:
            result = {
                "address": address,
                "snapshot_date": datetime.now(timezone.utc).isoformat(),
                "metrics": {},
                "summary": {},
                "data_quality": {
                    "trades_analyzed": 0,
                    "date_range": None,
                    "warning": f"数据获取失败: {error}"
                }
            }

            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            print(f"错误: {error}", file=sys.stderr)
            return

        # 2. 从数据库读取指标
        print("正在读取指标数据...", file=sys.stderr)
        db_data = read_metrics_from_db(tmp_db_path, address)

        # 3. 提取并格式化指标
        extracted = extract_metrics(db_data)

        # 4. 构建最终输出
        result = {
            "address": address,
            "snapshot_date": datetime.now(timezone.utc).isoformat(),
            **extracted
        }

        # 5. 写入输出文件
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"指标计算完成，已保存到 {args.output}", file=sys.stderr)

    finally:
        # 清理临时数据库
        if os.path.exists(tmp_db_path):
            try:
                os.unlink(tmp_db_path)
            except:
                pass


if __name__ == '__main__':
    main()
