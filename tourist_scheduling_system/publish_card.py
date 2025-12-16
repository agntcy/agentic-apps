
import os
import json
import logging
from pathlib import Path
from google.protobuf.struct_pb2 import Struct
from google.protobuf.json_format import ParseDict

from agntcy.dir_sdk.client import Client
from agntcy.dir_sdk.models import core_v1, routing_v1

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the oasf_records directory
A2A_CARDS_DIR = Path(__file__).parent / "oasf_records"

def publish_card(card_name: str):
    card_path = A2A_CARDS_DIR / f"{card_name}.json"
    if not card_path.exists():
        logger.error(f"Card file not found: {card_path}")
        return

    with open(card_path, "r") as f:
        card_data = json.load(f)

    # Add schema_version if missing (required by Directory)
    if "schema_version" not in card_data:
        card_data["schema_version"] = "1.0.0"

    # Initialize client
    # Ensure DIRECTORY_CLIENT_SERVER_ADDRESS is set or use default localhost:8888
    if "DIRECTORY_CLIENT_SERVER_ADDRESS" not in os.environ:
        os.environ["DIRECTORY_CLIENT_SERVER_ADDRESS"] = "localhost:8888"

    client = Client()

    # Create Record
    # The Record.data field is a Struct
    data_struct = Struct()
    ParseDict(card_data, data_struct)

    record = core_v1.Record(
        data=data_struct
    )

    logger.info(f"Pushing record for {card_name}...")
    try:
        # Push record to store
        refs = client.push([record])
        cid = refs[0].cid
        logger.info(f"Record pushed with CID: {cid}")

        # Publish record to routing
        logger.info(f"Publishing record {cid}...")

        # Create RecordRefs object
        record_refs = routing_v1.RecordRefs(
            refs=[core_v1.RecordRef(cid=cid)]
        )

        pub_req = routing_v1.PublishRequest(
            record_refs=record_refs
        )
        client.publish(pub_req)
        logger.info(f"Successfully published {card_name}")

    except Exception as e:
        logger.error(f"Failed to publish card: {e}")

if __name__ == "__main__":
    # Publish all cards
    cards = ["scheduler_agent", "guide_agent", "tourist_agent", "ui_agent"]
    for card in cards:
        publish_card(card)
