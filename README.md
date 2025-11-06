# Ozon Price Tracker Bot

![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/vshulcz/ozon_price_tracker?sort=semver)
[![CI](https://github.com/vshulcz/ozon_price_tracker/actions/workflows/ci.yml/badge.svg)](../../actions)
[![codecov](https://codecov.io/gh/vshulcz/ozon_price_tracker/branch/main/graph/badge.svg)](https://codecov.io/gh/vshulcz/ozon_price_tracker)
![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.11+-blue)
[![Telegram Demo](https://img.shields.io/badge/telegram-@mpricemonitoring__bot-2CA5E0?logo=telegram\&logoColor=white)](https://t.me/mpricemonitoring_bot)

A Telegram bot that tracks prices of Ozon products. Paste a product link, set a target price, and the bot checks prices three times a day and notifies you when the target is reached.

> [🇷🇺 Русская версия](README-ru.md)

## Quick start (Docker)

```bash
cp .env.example .env   # set BOT_TOKEN and DATABASE_URL
make up && make logs
```

## Usage Flow

1. Tap Add product and send a valid Ozon product URL.
2. The bot fetches product title and current price.
3. Enter a target price.
4. The product is stored and appears in Products. You can open its card and Edit target price, Open Ozon, or go Back.
5. The scheduler runs at 09:00, 15:00 and 21:00 (server time) and updates prices, storing history.
6. When current ≤ target, you receive a deal reached notification with a Remove product button.
7. If later current > target, you receive one deal over notification. Repeated notifications for the same state are suppressed.

## Internationalization

* RU 🇷🇺 and EN 🇬🇧 message dictionaries live in app/i18n.py.
* In bot: settings → choose language.

## Notes

* Scraping may violate Ozon T&Cs — use responsibly and at your own risk.
* The project is for educational/demo purposes.
* Try the demo: **[@mpricemonitoring_bot](https://t.me/mpricemonitoring_bot)**

## Contributing

* PRs are welcome - please run linters/tests locally and add coverage where possible.
* Star the repo ⭐ and share
