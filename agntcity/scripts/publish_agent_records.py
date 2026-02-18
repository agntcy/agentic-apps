# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""Automation script for publishing and managing agent records.

This module provides utilities for:
- Translating and validating agent records using OASF SDK
- Publishing agent records to the Agent Directory Service (ADS)
- Managing agent card records from various agent types
"""

# Standard library imports
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Tuple, List

# Third-party imports
import grpc
from google.protobuf.json_format import ParseDict, MessageToJson
from google.protobuf.struct_pb2 import Struct

logger = logging.getLogger(__name__)

# Check for required AGNTCY SDK imports
try:
    # AGNTCY SDK imports
    from agntcy.dir_sdk.client import Client, Config
    from agntcy.dir_sdk.models import core_v1, routing_v1
    from agntcy.oasfsdk.validation.v1.validation_service_pb2 import ValidateRecordRequest
    from agntcy.oasfsdk.validation.v1.validation_service_pb2_grpc import ValidationServiceStub
    from agntcy.oasfsdk.translation.v1.translation_service_pb2 import A2AToRecordRequest
    from agntcy.oasfsdk.translation.v1.translation_service_pb2_grpc import TranslationServiceStub
    from a2a.types import AgentCard
except ModuleNotFoundError as e:
    if "agntcy.dir_sdk" in str(e):
        logger.error("Missing required AGNTCY DIR SDK dependencies")
        logger.error("Please install dev dependencies by running:")
        logger.error("   uv sync --extra dev")
        logger.error("")
        logger.error(f"Original error: {e}")
        sys.exit(1)
    else:
        # Re-raise other ModuleNotFoundError exceptions
        raise

# Configuration constants
DEFAULT_OASF_HOST = "localhost"
DEFAULT_OASF_PORT = 31234
DEFAULT_ADS_ADDRESS = "localhost:8888"
DEFAULT_DIRCTL_PATH = "/usr/local/bin/dirctl"
DEFAULT_SCHEMA_VERSION = "1.0.0"
DEFAULT_LIST_LIMIT = 10
OASF_RECORDS_DIR = "oasf_records"

class OASFUtil:
    """Utility class for translating and validating agent records using OASF SDK.
    
    This class provides methods to:
    - Translate A2A AgentCards to OASF records
    - Validate OASF records
    - Convert between different record formats
    
    Translation and validation is performed by the oasf-sdk gRPC service.
    """

    def __init__(
        self, 
        host: str = DEFAULT_OASF_HOST, 
        port: int = DEFAULT_OASF_PORT, 
        auto_connect: bool = True
    ):
        """
        Initialize OASFUtil.

        Args:
            host: gRPC server host
            port: gRPC server port
            auto_connect: If True, establishes connection immediately.
                         If False, call connect() manually.
        """
        self.address = f"{host}:{port}"
        self._channel: Optional[grpc.Channel] = None
        self._translation_stub: Optional[TranslationServiceStub] = None
        self._validation_stub: Optional[ValidationServiceStub] = None
        self._managed_context = False

        if auto_connect:
            self.connect()

    def connect(self) -> None:
        """Establish gRPC connection and initialize stubs."""
        if self._channel is None:
            self._channel = grpc.insecure_channel(self.address)
            self._translation_stub = TranslationServiceStub(self._channel)
            self._validation_stub = ValidationServiceStub(self._channel)

    def close(self) -> None:
        """Close gRPC connection and cleanup resources."""
        if self._channel:
            self._channel.close()
            self._channel = None
            self._translation_stub = None
            self._validation_stub = None

    def __enter__(self):
        """Context manager entry - establishes gRPC connection."""
        self._managed_context = True
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes gRPC connection."""
        if self._managed_context:
            self.close()
            self._managed_context = False

    def __del__(self):
        """Cleanup on garbage collection."""
        self.close()

    def _oasf_sdk_record_to_dir_sdk_record(
        self, record_struct: Struct
    ) -> core_v1.Record:
        """
        Convert OASF record Struct to core_v1.Record.

        Args:
            record_struct: Protobuf Struct representation of the OASF record

        Returns:
            core_v1.Record instance
        """
        record_dict = json.loads(MessageToJson(record_struct))

        record = core_v1.Record()
        record.data.update(record_dict)

        return record

    def validate_oasf(self, record_data: dict) -> Tuple[bool, List[str]]:
        """Validate an OASF record.

        Args:
            record_data: Dictionary containing the OASF record to validate

        Returns:
            Tuple of (is_valid, errors) where errors is a list of error messages

        Raises:
            RuntimeError: If not connected
            grpc.RpcError: If the gRPC call fails
        """
        if not self._validation_stub:
            raise RuntimeError(
                "Not connected. Call connect() or use as context manager."
            )

        record_struct = Struct()
        record_struct.update(record_data)

        request = ValidateRecordRequest(record=record_struct)
        response = self._validation_stub.ValidateRecord(request)

        return response.is_valid, list(response.errors)
    
    def _dir_sdk_record_to_oasf_sdk_record(self, record: core_v1.Record) -> Struct:
        """
        Convert core_v1.Record to OASF record Struct.

        Args:
            record: core_v1.Record instance

        Returns:
            Protobuf Struct representation of the OASF record
        """
        record_dict = json.loads(MessageToJson(record.data))
        record_struct = Struct()
        record_struct.update(record_dict)

        return record_struct

    def a2a_to_oasf(self, agent_card: AgentCard, output_file: Optional[str] = None) -> core_v1.Record:
        """
        Translate an A2A AgentCard to an OASF record.

        Args:
            agent_card: The A2A AgentCard to translate

        Returns:
            Protobuf Struct containing the OASF record, or None if translation fails

        Raises:
            RuntimeError: If not connected
            grpc.RpcError: If the gRPC call fails
        """
        if not self._translation_stub:
            raise RuntimeError(
                "Not connected. Call connect() or use as context manager."
            )

        dict_agent_card = json.loads(agent_card.model_dump_json())
        data = {"a2aCard": dict_agent_card}

        record_struct = Struct()
        record_struct.update(data)

        request = A2AToRecordRequest(data=record_struct)
        response = self._translation_stub.A2AToRecord(request)

        # write to file if specified
        if output_file:
            with open(output_file, "w") as f:
                f.write(MessageToJson(response.record))

        # need to return a core_v1.Record
        return self._oasf_sdk_record_to_dir_sdk_record(response.record)

class AdsUtil:
    """Agent Directory Service (ADS) Registry implementation.
    
    This class provides methods to:
    - Push agent records to the directory
    - Publish records for routing
    - List existing agent records
    - Manage authentication and connection to ADS
    """
    
    def __init__(
        self,
        load_from_env: bool = False,
        server_address: str = DEFAULT_ADS_ADDRESS,
        dirctl_path: str = DEFAULT_DIRCTL_PATH,
        spiffe_socket_path: str = "",
        auth_mode: str = "",  # Options: "x509", "jwt", or "" for no auth
        jwt_audience: str = "",
    ):
        """Initialize ADS utility.
        
        Args:
            load_from_env: If True, load configuration from environment variables
            server_address: Address of the ADS server
            dirctl_path: Path to dirctl binary (required for signing)
            spiffe_socket_path: Path to SPIFFE socket (e.g., "/tmp/agent.sock")
            auth_mode: Authentication mode ("x509", "jwt", or "" for no auth)
            jwt_audience: JWT audience (e.g., "spiffe://example.org/dir-server")
        """
        self.client = None
        # create the the client
        try:
            self._create_client(
                load_from_env,
                auth_mode,
                server_address,
                dirctl_path,
                spiffe_socket_path,
                jwt_audience,
            )
        except Exception as e:
            logger.error(f"Failed to create ADS client: {e}")

    def push_agent_record(self, record: core_v1.Record) -> Optional[str]:
        """Push an agent record to the directory and publish it for routing.
        
        Args:
            record: The agent record to push and publish
            
        Returns:
            The CID of the published record, or None if failed
            
        Raises:
            Exception: If the client is not initialized or push/publish fails
        """
        if not self.client:
            logger.error("ADS client not initialized")
            return None
            
        try:
            # Push record to store
            refs = self.client.push([record])
            cid = refs[0].cid
            logger.info(f"Record pushed with CID: {cid}")

            # Publish record to routing
            logger.info(f"Publishing record {cid}...")
            record_refs = routing_v1.RecordRefs(refs=[core_v1.RecordRef(cid=cid)])
            pub_req = routing_v1.PublishRequest(record_refs=record_refs)
            self.client.publish(pub_req)
            
            logger.info(f"Successfully published record with CID: {cid}")
            return cid

        except Exception as e:
            logger.error(f"Failed to publish record: {e}")
            return None
        
    def list_agent_records(self, limit: int = DEFAULT_LIST_LIMIT) -> List[str]:
        """List agent records in the directory.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of JSON-formatted record strings
            
        Raises:
            Exception: If the client is not initialized or list operation fails
        """
        if not self.client:
            raise Exception("ADS client not initialized")
            
        list_request = routing_v1.ListRequest(limit=limit)
        objects = list(self.client.list(list_request))
        
        json_records = [MessageToJson(record) for record in objects]
        return json_records
        
    def _create_client(
        self,
        load_from_env,
        auth_mode,
        server_address,
        dirctl_path,
        spiffe_socket_path,
        jwt_audience,
    ):
        if load_from_env:
            logger.info(
                "Loading Dir SDK client configuration from environment variables"
            )
            self.client = Client()
            return
        # Initialize the Dir SDK client based on auth mode
        if auth_mode == "x509":
            config = Config(
                server_address=server_address,
                dirctl_path=dirctl_path,
                spiffe_socket_path=spiffe_socket_path,
                auth_mode=auth_mode,
            )
            logger.info("Using X.509 authentication with SPIRE")
        elif auth_mode == "jwt":
            config = Config(
                server_address=server_address,
                dirctl_path=dirctl_path,
                spiffe_socket_path=spiffe_socket_path,
                auth_mode=auth_mode,
                jwt_audience=jwt_audience,
            )
            logger.info("Using JWT authentication with SPIRE")
        else:
            logger.info("No authentication mode specified, defaulting to no auth.")
            config = Config(
                server_address=server_address,
                dirctl_path=dirctl_path,
            )

        self.client = Client(config)

def _ensure_schema_version(card_data: dict) -> None:
    """Ensure card data has a schema_version field (required by Directory)."""
    if "schema_version" not in card_data:
        card_data["schema_version"] = DEFAULT_SCHEMA_VERSION
        logger.debug(f"Added default schema_version: {DEFAULT_SCHEMA_VERSION}")


def _create_record_from_card_data(card_data: dict) -> core_v1.Record:
    """Create a core_v1.Record from card data dictionary."""
    data_struct = Struct()
    ParseDict(card_data, data_struct)
    return core_v1.Record(data=data_struct)


def publish_card(card_path: Path, directory: AdsUtil) -> Optional[str]:
    """Publish an agent card from a file to the directory.
    
    Args:
        card_path: Path to the JSON card file
        directory: AdsUtil instance for publishing
        
    Returns:
        The CID of the published record, or None if failed
        
    Raises:
        FileNotFoundError: If the card file doesn't exist
        json.JSONDecodeError: If the card file is not valid JSON
    """
    try:
        with open(card_path, "r") as f:
            card_data = json.load(f)
        
        _ensure_schema_version(card_data)
        record = _create_record_from_card_data(card_data)
        
        logger.info(f"Pushing record for {card_path.stem}...")
        return directory.push_agent_record(record)
        
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load card from {card_path}: {e}")
        return None

def _import_agent_cards() -> List[AgentCard]:
    """Import all available agent cards.
    
    Returns:
        List of AgentCard objects
        
    Raises:
        ImportError: If any required agent cards cannot be imported
    """
    try:
        # Farm agent cards
        from agents.farms.brazil.card import AGENT_CARD as BRAZIL_AGENT_CARD
        from agents.farms.vietnam.card import AGENT_CARD as VIETNAM_AGENT_CARD
        from agents.farms.colombia.card import AGENT_CARD as COLOMBIA_AGENT_CARD

        # Logistics agent cards
        from agents.logistics.accountant.card import AGENT_CARD as ACCOUNTANT_AGENT_CARD
        from agents.logistics.farm.card import AGENT_CARD as LOGISTICS_FARM_AGENT_CARD
        from agents.logistics.helpdesk.card import AGENT_CARD as HELPDESK_AGENT_CARD
        from agents.logistics.shipper.card import AGENT_CARD as SHIPPER_AGENT_CARD

        # TODO: Add supervisor agent cards when available

        return [
            BRAZIL_AGENT_CARD,
            VIETNAM_AGENT_CARD,
            COLOMBIA_AGENT_CARD,
            ACCOUNTANT_AGENT_CARD,
            LOGISTICS_FARM_AGENT_CARD,
            HELPDESK_AGENT_CARD,
            SHIPPER_AGENT_CARD,
        ]
    except ImportError as e:
        logger.error(f"Failed to import agent cards: {e}")
        raise


def _process_agent_card(agent_card: AgentCard, oasf_util: OASFUtil, directory: AdsUtil, cleanup: bool = False) -> Optional[str]:
    """Process a single agent card - translate, publish, and clean up.
    
    Args:
        agent_card: The agent card to process
        oasf_util: OASF utility instance
        directory: ADS utility instance
        
    Returns:
        True if successful, False otherwise
    """


    # create a file_name that removes any spaces or special characters
    file_name = agent_card.name.replace(" ", "_").rstrip()
    card_file = f"{OASF_RECORDS_DIR}/{file_name}.json"

    logger.debug(f"file_name: {file_name}")
    
    try:
        # Translate A2A card to OASF record
        logger.info(f"Processing agent card: {agent_card.name}")
        oasf_util.a2a_to_oasf(agent_card, output_file=card_file)

        # Publish the OASF record
        cid = publish_card(Path(card_file), directory)
        
        if cid:
            logger.info(f"Successfully published {agent_card.name} with CID: {cid}")
            return cid
        else:
            logger.error(f"Failed to publish {agent_card.name}")
            return None
            
    except Exception as e:
        logger.error(f"Error processing agent card {agent_card.name}: {e}")
        return None
        
    finally:
        if cleanup:
            card_file = f"{OASF_RECORDS_DIR}/{file_name}.json"
            Path(card_file).unlink(missing_ok=True)


def publish_lungo_agent_records(cid_output_file: Optional[str] = None) -> bool:
    """Publish all Lungo agent records to the directory.
    
    Returns:
        True if all records were published successfully, False otherwise
    """
    try:
        directory = AdsUtil()
        oasf_util = OASFUtil()
    except Exception as e:
        logger.error(f"Failed to initialize required services: {e}")
        return False
    
    try:
        agent_cards = _import_agent_cards()
    except ImportError:
        return False
    
    success_count = 0
    total_count = len(agent_cards)
    cids = {}
    
    logger.info(f"Publishing {total_count} agent records...")
    
    for agent_card in agent_cards:
        cid = _process_agent_card(agent_card, oasf_util, directory)
        if cid:
            cids[agent_card.name] = cid
            success_count += 1
    
    logger.info(f"Published {success_count}/{total_count} agent records successfully")

    if cid_output_file:
        try:
            with open(cid_output_file, "w") as f:
                json.dump(cids, f, indent=2)
            logger.info(f"Wrote published CIDs to {cid_output_file}")
        except Exception as e:
            logger.error(f"Failed to write CIDs to file: {e}")
    return success_count == total_count

def main(cid_output_file="published_cids.json") -> None:
    """Main entry point for the automation script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # clear the previous output file if it exists or create a new one if not
    Path(cid_output_file).write_text("")
    
    logger.info("Starting Lungo agent record publishing...")
    success = publish_lungo_agent_records(cid_output_file=cid_output_file)
    
    if success:
        logger.info("✅ All agent records published successfully")
    else:
        logger.error("Some agent records failed to publish")
        exit(1)


if __name__ == "__main__":
    main()