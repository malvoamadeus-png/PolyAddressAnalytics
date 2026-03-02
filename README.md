# Wallet Metrics Skill

快速计算 Polymarket 钱包地址的核心交易指标。

## 功能

为单个 Polymarket 钱包地址计算 8 个核心交易指标：

1. **ROI (投资回报率)** — 总盈亏 / 成本基础
2. **Sharpe Ratio (夏普比率)** — 风险调整后收益
3. **Profit Factor (获利因子)** — 总盈利 / 总亏损
4. **Max Drawdown (最大回撤)** — 权益曲线最大跌幅
5. **Win Rate (胜率)** — 盈利交易占比
6. **Position Size CV (仓位规模变异系数)** — 下注金额一致性
7. **HHI (市场集中度指数)** — 资金分散程度
8. **Current Position Value (当前持仓价值)** — 开仓持仓总价值

## 使用方法

### 通过 Claude Code

直接向 Claude 提供钱包地址：

```
Get metrics for wallet 0x1234567890abcdef1234567890abcdef12345678
```

Claude 会自动调用此技能并返回指标。

### 直接运行脚本

```bash
cd .trae/skills/wallet-metrics
python scripts/compute_wallet_metrics.py \
  --address 0x1234567890abcdef1234567890abcdef12345678 \
  --output /tmp/metrics.json
```

## 输出示例

```json
{
  "address": "0x...",
  "snapshot_date": "2026-03-02T12:34:56.789Z",
  "metrics": {
    "roi": 0.45,
    "sharpe_ratio": 1.23,
    "profit_factor": 2.15,
    "max_drawdown": 0.18,
    "win_rate": 0.62,
    "position_size_cv": 0.85,
    "hhi": 0.32,
    "current_position_value_usd": 3200.00
  },
  "summary": {
    "total_pnl": 12500.50,
    "total_trades": 145,
    "winning_trades": 90,
    "losing_trades": 55
  },
  "data_quality": {
    "trades_analyzed": 145,
    "date_range": "2024-01-15 to 2026-03-02",
    "warning": null
  }
}
```

## 指标解读

### ROI (投资回报率)
- **> 50%** — 优秀
- **20%-50%** — 良好
- **0%-20%** — 正回报但一般
- **< 0%** — 亏损

### Sharpe Ratio (夏普比率)
- **> 2.0** — 优秀风险调整收益
- **1.0-2.0** — 良好
- **< 1.0** — 一般

### Profit Factor (获利因子)
- **> 2.0** — 优秀（每亏 1 美元赚 2 美元以上）
- **1.5-2.0** — 良好
- **< 1.0** — 亏损

### Max Drawdown (最大回撤)
- **< 10%** — 优秀风险控制
- **10%-20%** — 良好
- **> 30%** — 高风险

### Win Rate (胜率)
- **> 60%** — 优秀
- **55%-60%** — 良好
- **< 50%** — 低于平均

### Position Size CV (仓位规模变异系数)
- **< 0.5** — 非常一致
- **0.5-1.0** — 一致
- **> 2.0** — 不一致

### HHI (市场集中度)
- **< 0.25** — 分散
- **0.25-0.5** — 中等集中
- **> 0.5** — 高度集中

### Current Position Value (当前持仓价值)
- 表示当前风险敞口
- 与总资产比例反映杠杆使用

## 执行时间

典型执行时间：**10-20 秒**

## 限制

- **单地址查询** — 不支持批量或多账户比较
- **无策略分析** — 不进行策略分类
- **无排行榜** — 不扫描顶级交易者
- **无缓存** — 每次查询获取最新数据
- **JSON 输出** — 无叙述性报告

如需策略分析或排行榜功能，使用 `polymarket-analyst` 技能。

## 数据来源

所有数据来自 Polymarket 公开 API：
- Gamma API — 持仓数据
- Data API — 已平仓持仓
- User PnL API — PnL 时间序列
- CLOB API — 当前持仓价值

无需 API 密钥。

## 依赖

```bash
pip install -r scripts/requirements.txt
```

依赖项：
- `requests>=2.28.0`

**无需 PolySport 项目文件** — 此技能完全独立，可在任何环境运行。

## 文件结构

```
.trae/skills/wallet-metrics/
├── SKILL.md                          # Claude 指令
├── README.md                         # 本文档
├── .claude/
│   └── settings.local.json          # 权限配置
├── scripts/
│   ├── compute_wallet_metrics.py    # 主脚本
│   └── requirements.txt             # Python 依赖
├── references/
│   └── metrics_definitions.md       # 指标定义（中英双语）
└── evals/
    └── evals.json                   # 测试用例
```

## 技术细节

脚本直接调用 Polymarket API 并内嵌所有计算逻辑：
- `fetch_positions()` — 获取开仓持仓
- `fetch_closed_positions()` — 获取已平仓持仓
- `fetch_user_pnl_series()` — 获取 PnL 时间序列
- `compute_metrics_snapshot()` — 计算 Profit Factor 和 ROI
- `compute_pnl_drawdown_sharpe()` — 计算 Max Drawdown 和 Sharpe Ratio
- `compute_position_based_stats()` — 计算 Win Rate
- `compute_position_size_cv()` — 计算仓位规模变异系数
- `compute_hhi()` — 计算市场集中度指数

**完全独立** — 所有逻辑内嵌在 `compute_wallet_metrics.py` 中，无外部依赖。

## 错误处理

### 地址未找到
输出 `data_quality.warning: "未找到交易历史"`

### 交易数量少 (< 20)
输出警告但仍计算指标

### 部分指标缺失
某些指标可能为 `null`（如 Sharpe Ratio 需要 PnL 时间序列）

### API 速率限制
自动重试（指数退避）

## 许可

本技能是 PolySport 项目的一部分。
