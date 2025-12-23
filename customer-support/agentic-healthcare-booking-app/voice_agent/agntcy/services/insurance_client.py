# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import re
import os
import requests
from http import HTTPStatus
from ioa_observe.sdk.decorators import tool
from ioa_observe.sdk.instrumentations.mcp import McpInstrumentor
from ioa_observe.sdk import Observe
from datetime import datetime

class InsuranceClient:
    def __init__(self, mcp_url, api_key):
        self.mcp_url = mcp_url
        self.headers = {"Content-Type": "application/json", "X-INF-API-KEY": api_key}
        
        # Initialize Observe SDK for MCP instrumentation
        api_endpoint = os.getenv('OTLP_ENDPOINT', 'http://localhost:4318')
        Observe.init("insurance_mcp_client", api_endpoint=api_endpoint)
        
        # Instrument MCP protocol interactions
        # Note: This instruments MCP client calls made via requests
        # For full MCP server instrumentation, see observe SDK examples
        McpInstrumentor().instrument()
        
        print("INSURANCE: Client initialized with MCP instrumentation")
    
    def _split_name(self, name):
        parts = name.strip().split()
        if len(parts) == 1:
            return parts[0], ""
        elif len(parts) == 2:
            return parts[0], parts[1]
        else:
            return parts[0], " ".join(parts[1:])
    
    def _format_dob(self, dob):
        if not dob:
            return ""
        
        if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', dob):
            month, day, year = dob.split('/')
            formatted = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            return formatted
        
        if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', dob):
            return dob
        
        return dob
    
    @tool(name="insurance_discovery_tool")
    async def discovery(self, name, dob, state):
        print(f"INSURANCE: Discovery - {name}, {dob}, {state}")
        first, last = self._split_name(name)
        formatted_dob = self._format_dob(dob)
        formatted_state = state.strip().title() if state else ""
        
        payload = {
            "jsonrpc": "2.0",
            "id": f"discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "method": "tools/call",
            "params": {
                "name": "insurance_discovery",
                "arguments": {
                    "patientDateOfBirth": formatted_dob,
                    "patientFirstName": first,
                    "patientLastName": last,
                    "patientState": formatted_state
                }
            }
        }
        
        def _request():
            return requests.post(self.mcp_url, headers=self.headers, json=payload, timeout=45)
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _request)
        
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            
            if "result" in data:
                result_text = str(data["result"])
                
                payer = ""
                member_id = ""
                
                for pattern in [r'payer[:\s]*([^\n,;]+)', r'insurance[:\s]*([^\n,;]+)', r'plan[:\s]*([^\n,;]+)']:
                    match = re.search(pattern, result_text.lower())
                    if match:
                        payer = match.group(1).strip().title()
                        break
                
                for pattern in [r'member\s*id[:\s]*([a-za-z0-9\-]+)', r'subscriber\s*id[:\s]*([a-za-z0-9\-]+)', r'policy\s*id[:\s]*([a-za-z0-9\-]+)', r'policy[:\s]*([a-za-z0-9\-]+)']:
                    match = re.search(pattern, result_text.lower())
                    if match:
                        member_id = match.group(1).strip().upper()
                        break
                
                return {"success": True, "payer": payer, "member_id": member_id}
        
        return {"success": False}
    
    @tool(name="insurance_eligibility_tool")
    async def eligibility(self, name, dob, subscriber_id, payer_name, provider_name):
        print(f"INSURANCE: Eligibility check")
        first, last = self._split_name(name)
        formatted_dob = self._format_dob(dob)
        
        provider_clean = re.sub(r'\b(Dr\.?|MD|DO)\b', '', provider_name, flags=re.IGNORECASE).strip()
        provider_first, provider_last = self._split_name(provider_clean)
        
        payload = {
            "jsonrpc": "2.0",
            "id": f"eligibility_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "method": "tools/call",
            "params": {
                "name": "benefits_eligibility",
                "arguments": {
                    "patientFirstName": first,
                    "patientLastName": last,
                    "patientDateOfBirth": formatted_dob,
                    "subscriberId": subscriber_id,
                    "payerName": payer_name,
                    "providerFirstName": provider_first,
                    "providerLastName": provider_last,
                    "providerNpi": "1234567890"
                }
            }
        }
        
        def _request():
            return requests.post(self.mcp_url, headers=self.headers, json=payload, timeout=45)
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _request)
        
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            
            if "result" in data:
                result_text = str(data["result"])
                
                copay = ""
                copay_patterns = [r'co-?pay[:\s]*\$?([0-9,]+)', r'copayment[:\s]*\$?([0-9,]+)', r'patient\s+responsibility[:\s]*\$?([0-9,]+)']
                
                for pattern in copay_patterns:
                    copay_match = re.search(pattern, result_text.lower())
                    if copay_match:
                        copay = copay_match.group(1)
                        break
                
                return {"success": True, "copay": copay}
        
        return {"success": False}