# Implementation Notes

## Architecture Decision (Updated)

This skill is **completely self-contained** with all logic embedded directly in the script.

**Previous approach (deprecated):**
- ❌ Called `polymarket_metrics.py` as subprocess
- ❌ Required root project files
- ❌ Not portable

**Current approach:**
- ✅ **Fully portable** - Works anywhere Python + requests available
- ✅ **No external dependencies** - All code in skill folder
- ✅ **No subprocess calls** - Direct API interaction
- ✅ **No database** - Direct computation and output

**Trade-off:** ~500 lines of code duplicated from `polymarket_metrics.py`, but ensures true portability.

## How It Works

```
User Request
    ↓
Claude invokes wallet-metrics skill
    ↓
compute_wallet_metrics.py
    ↓
Direct API calls to Polymarket
    ↓
Compute all 8 metrics in-memory
    ↓
Format as JSON
    ↓
Return to user
```

## Metrics Computed

All metrics are computed directly by embedded functions:

1. **roi** - Total PnL / Cost Basis
2. **sharpe_ratio** - Risk-adjusted returns from PnL series
3. **profit_factor** - Gross profit / Gross loss (per-market aggregation)
4. **max_drawdown** - Peak-to-trough decline in PnL series
5. **win_rate** - Winning positions / Total positions
6. **position_size_cv** - StdDev / Mean of buy amounts
7. **hhi** - Market concentration (Σ(share_i)²)
8. **current_position_value_usd** - Sum of open position values

## Embedded Functions

Copied from `polymarket_metrics.py`:
- API constants and `_RateLimiter` class
- `http_get_json()` with retry logic
- `fetch_positions()`, `fetch_closed_positions()`, `fetch_user_pnl_series()`
- `extract_position_fields()` for parsing position data
- `compute_metrics_snapshot()` for ROI and Profit Factor
- `compute_pnl_drawdown_sharpe()` for Sharpe and Max Drawdown
- `compute_position_based_stats()` for Win Rate
- `compute_position_size_cv()` for Position Size CV
- `compute_hhi()` for Market concentration

## Dependencies

- Python 3.7+
- `requests` library only

**No root project files required.**

## Execution Time

- Typical: 10-30 seconds
- Depends on API response times and trade count

## Testing

```bash
# Test with null address (should report no trading history)
python skills/wallet-metrics/scripts/compute_wallet_metrics.py \
  --address 0x0000000000000000000000000000000000000000 \
  --output /tmp/test.json

# Test with real address
python skills/wallet-metrics/scripts/compute_wallet_metrics.py \
  --address 0x6d3c5bd13984b2de47c3a88ddc455309aab3d294 \
  --output /tmp/test.json

# Portability test - copy to different directory
cd /tmp
cp -r /path/to/skills/wallet-metrics ./
cd wallet-metrics
pip install -r scripts/requirements.txt
python scripts/compute_wallet_metrics.py --address 0x6d3c5bd13984b2de47c3a88ddc455309aab3d294 --output out.json
```
