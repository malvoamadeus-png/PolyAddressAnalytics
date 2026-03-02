# Polymarket 指标定义 / Metrics Definitions

本文档定义 wallet-metrics 技能计算的 8 个核心交易指标。

---

## 1. Profit Factor (获利因子)

**中文定义：** 总盈利除以总亏损，衡量每承担 1 美元风险所赚取的美元数。

**English Definition:** Gross profit divided by gross loss; measures profitability per dollar risked.

**计算方法：**
1. 按市场聚合所有已平仓持仓的 PnL
2. 分别求和正 PnL（总盈利）和负 PnL（总亏损）
3. Profit Factor = 总盈利 / |总亏损|

**解读：**
- **> 2.0** — 优秀（每亏 1 美元赚 2 美元以上）
- **1.5 - 2.0** — 良好
- **1.0 - 1.5** — 盈利但效率一般
- **< 1.0** — 亏损

**数据来源：** 持仓数据中的 `pnl` 字段（按市场聚合）

---

## 2. ROI (投资回报率 / Return on Investment)

**中文定义：** 总盈亏除以成本基础，表示投资资本的百分比回报。

**English Definition:** Total PnL divided by cost basis; percentage return on invested capital.

**计算方法：**
1. 成本基础 = 所有 BUY 交易的 USD 支出总和
2. 总盈亏 = 所有已平仓持仓的 PnL 总和
3. ROI = 总盈亏 / 成本基础

**解读：**
- **> 0.5 (50%)** — 优秀回报
- **0.2 - 0.5 (20%-50%)** — 良好回报
- **0 - 0.2 (0%-20%)** — 正回报但一般
- **< 0** — 亏损

**数据来源：** 交易记录中的 `side` 和 `usd_amount` 字段

---

## 3. Position Size CV (仓位规模变异系数 / Coefficient of Variation)

**中文定义：** BUY 交易金额的标准差除以均值，衡量下注金额的一致性。

**English Definition:** Standard deviation divided by mean of buy amounts; measures bet sizing consistency.

**计算方法：**
1. 提取所有 BUY 交易的 USD 金额（过滤 < $1 的交易）
2. 计算均值 μ 和标准差 σ
3. CV = σ / μ

**解读：**
- **< 0.5** — 非常一致的仓位管理
- **0.5 - 1.0** — 一致的仓位管理
- **1.0 - 2.0** — 仓位大小波动较大
- **> 2.0** — 仓位管理不一致

**数据来源：** 交易记录中 `side='BUY'` 的 `usd_amount` 字段

---

## 4. HHI (赫芬达尔-赫希曼指数 / Herfindahl-Hirschman Index)

**中文定义：** 市场集中度指数，衡量资金在不同市场的分散程度。

**English Definition:** Market concentration index; measures diversification across markets.

**计算方法：**
1. 按市场分组所有开仓持仓
2. 计算每个市场的份额：s_i = V_i / V_total
3. HHI = Σ(s_i²)

**解读：**
- **< 0.15** — 高度分散（10+ 个市场均匀分布）
- **0.15 - 0.25** — 分散
- **0.25 - 0.5** — 中等集中
- **> 0.5** — 高度集中（少数市场占主导）

**数据来源：** 开仓持仓的 `market_slug` 和 `position_value_usd` 字段

---

## 5. Max Drawdown (最大回撤)

**中文定义：** 权益曲线从峰值到谷底的最大跌幅百分比，衡量最坏连续亏损期。

**English Definition:** Peak-to-trough decline in equity curve; measures worst losing streak.

**计算方法：**
1. 从 PnL 时间序列构建累计权益曲线
2. 对每个点计算从历史最高点的回撤：(Peak - Current) / Peak
3. Max Drawdown = 所有回撤的最大值

**解读：**
- **< 0.1 (10%)** — 优秀风险控制
- **0.1 - 0.2 (10%-20%)** — 良好风险控制
- **0.2 - 0.3 (20%-30%)** — 中等风险
- **> 0.3 (30%)** — 高风险

**数据来源：** User PnL API 的时间序列数据

---

## 6. Sharpe Ratio (夏普比率)

**中文定义：** 风险调整后收益，每单位波动率的平均收益。

**English Definition:** Risk-adjusted return; average return per unit of volatility.

**计算方法：**
1. 从 PnL 时间序列计算每日 PnL
2. 计算日均 PnL (μ) 和日 PnL 标准差 (σ)
3. Sharpe Ratio = (μ / σ) × √365（年化）

**解读：**
- **> 2.0** — 优秀风险调整收益
- **1.0 - 2.0** — 良好风险调整收益
- **0.5 - 1.0** — 中等风险调整收益
- **< 0.5** — 风险调整收益较差

**数据来源：** User PnL API 的时间序列数据

---

## 7. Win Rate (胜率)

**中文定义：** 盈利交易占总交易的百分比。

**English Definition:** Percentage of profitable positions out of total trades.

**计算方法：**
1. 统计所有已平仓持仓
2. 盈利交易 = PnL > 0 的持仓数
3. Win Rate = 盈利交易 / 总交易数

**解读：**
- **> 0.6 (60%)** — 优秀胜率
- **0.55 - 0.6 (55%-60%)** — 良好胜率
- **0.5 - 0.55 (50%-55%)** — 中等胜率
- **< 0.5 (50%)** — 胜率低于 50%

**注意：** 高胜率不一定意味着高盈利（需结合 Profit Factor 和 ROI）

**数据来源：** 已平仓持仓的 `pnl` 字段

---

## 8. Current Position Value (当前持仓价值)

**中文定义：** 所有开仓持仓的当前 USD 市场价值总和。

**English Definition:** Total USD market value of all open positions.

**计算方法：**
1. 调用 Polymarket CLOB API 获取当前持仓价值
2. 返回 USD 总值

**解读：**
- 表示当前风险敞口
- 与账户总资产的比例反映杠杆使用情况
- 高持仓价值 + 低 Max Drawdown = 良好风险管理

**数据来源：** CLOB API 的 `/positions` 端点

---

## 数据清洗规则

所有指标计算前应用以下数据清洗规则（与根目录 `polymarket_metrics.py` 一致）：

1. **过滤小额交易** — 忽略 USD 金额 < $1 的交易
2. **去重** — 按交易哈希去重（避免重复计数）
3. **对冲合并** — 同一市场的 YES/NO 对冲持仓合并为净持仓

---

## 权威参考

本文档的指标定义源自项目根目录的 `新统计设计标准.md`（中文权威文档）。

如有冲突，以 `新统计设计标准.md` 为准。
