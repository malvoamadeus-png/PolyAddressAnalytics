# Implementation Notes

## Architecture Decision

This skill is **self-contained** and does not import code from the root codebase. Instead, it:

1. **Calls `polymarket_metrics.py` as a subprocess** with a temporary SQLite database
2. **Reads the results** from the temporary database
3. **Formats the output** as JSON with 8 core metrics

This approach ensures:
- ✅ **Skill independence** - No Python imports from root code
- ✅ **Code reuse** - Leverages battle-tested metric computation logic
- ✅ **Maintainability** - No duplicate code to keep in sync
- ✅ **Portability** - Skill can be moved/shared independently

## How It Works

```
User Request
    ↓
Claude invokes wallet-metrics skill
    ↓
compute_wallet_metrics.py
    ↓
subprocess: python polymarket_metrics.py --address 0x... --db /tmp/xxx.sqlite
    ↓
Read metrics from SQLite
    ↓
Format as JSON with 8 metrics
    ↓
Return to user
```

## Metrics Extracted

The script reads from the `address_metrics` table and extracts:

1. **roi** - From `roi` column
2. **sharpe_ratio** - From `sharpe` column
3. **profit_factor** - From `profit_factor` column
4. **max_drawdown** - From `max_drawdown` column
5. **win_rate** - From `win_rate` column
6. **position_size_cv** - From `position_size_cv` column
7. **hhi** - From `hhi` column
8. **current_position_value_usd** - From `current_position_value_usd` column

All metrics are computed by the root `polymarket_metrics.py` script.

## Dependencies

- Python 3.7+
- `requests` library (used by root script)
- Root `polymarket_metrics.py` must exist

## Execution Time

- Typical: 10-30 seconds
- Depends on API response times and trade count

## Testing

```bash
# Test with null address (should report no trading history)
python .trae/skills/wallet-metrics/scripts/compute_wallet_metrics.py \
  --address 0x0000000000000000000000000000000000000000 \
  --output /tmp/test.json

# Test with real address
python .trae/skills/wallet-metrics/scripts/compute_wallet_metrics.py \
  --address 0x<real_address> \
  --output /tmp/test.json
```
