#!/usr/bin/env python

import os
from pathlib import Path

ROOT = Path(__file__).parent.parent

ENV = [
    "PATH",
    "DATABASE_URL",
    "DJANGO_SETTINGS_MODULE",
    "TOPSCORE_CLIENT_ID",
    "TOPSCORE_CLIENT_SECRET",
    "TOPSCORE_SITE_SLUG",
    "TOPSCORE_USERNAME",
    "TOPSCORE_PASSWORD",
    "RAZORPAY_KEY_ID",
    "RAZORPAY_KEY_SECRET",
    "RAZORPAY_WEBHOOK_SECRET",
    "PAYMENT_ACCOUNT_ENCRYPTION_KEY",
    "CLOUDINARY_API_SECRET",
    "CLOUDINARY_MEDIA_PREFIX",
    "FLY_APP_NAME",
]


def main() -> None:
    cron_dir = ROOT / "cron"
    os.makedirs(cron_dir, exist_ok=True)
    with open(cron_dir / "env", "w") as f:
        for var in ENV:
            value = os.environ.get(var)
            if value is not None:
                f.write(f"export {var}={value}\n")
        f.write("cd $HOME/app\n")


if __name__ == "__main__":
    main()
