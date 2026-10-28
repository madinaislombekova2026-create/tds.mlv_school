import logging
import sys
import uvicorn
from bot.config import load_config
from bot.webhook.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("main")

def main():
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    logger.info(f"Starting server on port {config.PORT}...")
    app = create_app(config)
    uvicorn.run(app, host="0.0.0.0", port=config.PORT, access_log=True)


if __name__ == "__main__":
    main()
