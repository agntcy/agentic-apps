# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import logging
import argparse
import sys
from pathlib import Path
from service.triage_service import A2ATriageService
from ioa_observe.sdk.instrumentations.a2a import A2AInstrumentor
import os
from dotenv import load_dotenv


app_dir = Path(__file__).resolve().parent.parent.parent.parent
common_dir = app_dir/ 'common'
sys.path.insert(0, str(common_dir))
from agntcy.observe.observe_config import initialize_observability

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(description='A2A Medical Triage Service with TBAC')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8887, help='Port to bind to (default: 8887)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--disable-tbac', action='store_true', help='Disable TBAC authorization')
    
    args = parser.parse_args()
    
    try:
        load_dotenv()
        initialize_observability("a2a_triage_service")
        A2AInstrumentor().instrument()
        service = A2ATriageService(
            host=args.host,
            port=args.port,
            debug=args.debug,
            enable_tbac=not args.disable_tbac
        )
        service.run()
    except Exception as e:
        logger.error(f"Failed to start service: {e}", exc_info=True)
        exit(1)

if __name__ == "__main__":
    main()