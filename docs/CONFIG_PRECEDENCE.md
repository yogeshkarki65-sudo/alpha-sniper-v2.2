# Configuration Loading Precedence

## Overview
Alpha Sniper v4.1.1 follows a strict configuration precedence order to ensure predictable behavior.

## Precedence Order (Highest to Lowest)

```
1. Environment Variables (.env file or shell exports)
2. Config Class Defaults (config/config.py)
```

## How It Works

### 1. Environment Variables (Highest Priority)
Values set in `.env` file or exported in shell override all defaults.

```bash
# .env
MIN_SIGNAL_SCORE=70
MAX_CONCURRENT_POS=2
STOP_LOSS_PCT=5.0
```

These will **always** take precedence over code defaults.

### 2. Config Class Defaults (Fallback)
If an environment variable is not set, the default in `config.py` is used:

```python
MIN_SIGNAL_SCORE = float(os.getenv('MIN_SIGNAL_SCORE', 70))
#                                                       ^^
#                                                  This is the default
```

## Best Practices

### ✅ DO:
- Set all critical parameters in `.env`
- Use `.env.example` as template
- Document any changes to defaults in commit messages
- Verify loaded config at startup (check console output)

### ❌ DON'T:
- Mix shell exports and .env file values (confusing)
- Modify `config.py` defaults without updating `.env.example`
- Assume config changes work without restarting the bot
- Use different configs in different terminals (use one .env)

## Verification

### At Startup
Alpha Sniper prints the full filter configuration showing all loaded values:

```
ENTRY FILTERS ACTIVE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Signal Scoring:
  • Min Signal Score: 70
  • Check Orderbook Imbalance: True
...
```

**Always verify these values match your expectations.**

### Debug Mode
Enable debug logging:

```bash
DEBUG_FILTERS=true
```

This will log every filter rejection with details, helping you verify filter behavior.

## Common Issues

### Issue: Config changes not taking effect
**Solution:** Restart the bot. Config is loaded once at startup.

### Issue: Different behavior than expected
**Solution:** Check startup output to see what values were actually loaded.

### Issue: Don't know what's overriding what
**Solution:**
1. Check `.env` file first
2. Check shell with `env | grep MIN_SIGNAL_SCORE`
3. Check `config.py` defaults

## Config Override Examples

### Example 1: Tighten Filters
```bash
# .env
MIN_SIGNAL_SCORE=75
STOP_LOSS_PCT=4.0
```

### Example 2: Loosen for Testing
```bash
# .env
MIN_SIGNAL_SCORE=60
MAX_CONCURRENT_POS=5
```

### Example 3: Debug Mode
```bash
# .env
DEBUG_FILTERS=true
```

## Environment Variable Types

Alpha Sniper automatically converts env vars to the correct type:

| Type | Example | Conversion |
|------|---------|------------|
| float | `70` | `float(os.getenv(...))` |
| int | `2` | `int(os.getenv(...))` |
| bool | `true` | `.lower() == 'true'` |
| string | `MEXC` | Direct string |

## Safety Checks

Current safeguards in place:
- ✅ All numeric values have sensible defaults
- ✅ Boolean values default to safe behavior (e.g., trading paused = false)
- ✅ Startup output shows all loaded config
- ✅ Filter debug mode available for transparency

## Future Improvements

Planned enhancements:
- [ ] Config validation on startup (warn if values seem wrong)
- [ ] Config file validation tool
- [ ] Hot-reload for non-critical settings
- [ ] Config history/versioning
