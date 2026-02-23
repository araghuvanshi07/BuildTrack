import os

import uvicorn


def main() -> None:
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8002'))
    reload_enabled = os.getenv('RELOAD', 'true').lower() in {'1', 'true', 'yes'}

    uvicorn.run(
        'app.main:app',
        host=host,
        port=port,
        reload=reload_enabled,
    )


if __name__ == '__main__':
    main()
