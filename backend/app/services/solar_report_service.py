"""Service for generating structured solar sales reports (Section 7)."""

import asyncio
import json
from typing import Any, Dict

from openai import AzureOpenAI, OpenAI

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger("services.solar_report")

SECTION_7_PROMPT = """
You are an expert sales analyst for Ujjwal Energies, a solar panel company in India.
Analyze the provided transcript of a sales call and extract the data into the following JSON
structure.
Be accurate and concise. If a value is unknown, use null or "unknown" as specified in the schema.

SCHEMA:
{
  "customer_info": {
    "name": "<customer_name>",
    "contact_number": "<phone_number>",
    "contact_person_for_visit": "<name_or_same_as_customer>",
    "address": "<full_address_or_null>",
    "city": "<city_or_null>",
    "preferred_language": "hindi | english | other"
  },
  "requirement": {
    "installation_type": "residential | commercial | industrial | unknown",
    "estimated_kw": "<number_or_unknown>",
    "monthly_electricity_bill": "<amount_or_unknown>",
    "preferred_brand": "<brand_name_or_no_preference>",
    "rooftop_available": "yes | no | unknown",
    "existing_solar": "yes | no | unknown"
  },
  "interests": {
    "subsidy_interested": true | false,
    "loan_emi_required": true | false,
    "net_metering_interested": true | false,
    "battery_storage_interested": true | false
  },
  "visit": {
    "visit_scheduled": true | false,
    "visit_date": "<date_or_null>",
    "visit_time_slot": "<morning|afternoon|evening_or_null>",
    "visit_address": "<address_if_different_from_customer_address>"
  },
  "lead_classification": {
    "lead_status": "hot | warm | cold | not_interested | callback | invalid_number",
    "confidence_score": <1-10>,
    "buying_timeline": "immediate | 1_month | 3_months | 6_months | no_timeline | not_interested"
  },
  "call_analysis": {
    "objections_raised": ["<objection_1>", "<objection_2>"],
    "competitors_mentioned": ["<competitor_name>"],
    "key_concerns": ["<concern_1>", "<concern_2>"],
    "positive_signals": ["<signal_1>", "<signal_2>"],
    "call_outcome": "<one_line_summary>",
    "call_summary_hindi": "<2-3 line summary in Hindi>",
    "next_action": "<specific_next_step>",
    "follow_up_required": true | false,
    "follow_up_date": "<date_or_null>",
    "follow_up_notes": "<notes_for_next_call>"
  }
}

TRANSCRIPT:
{transcript}
"""

class SolarReportService:
    def __init__(self):
        self.client, self.model = self._get_client()

    def _get_client(self):
        if settings.azure_openai_api_key:
            return AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
            ), settings.azure_openai_deployment
        return OpenAI(api_key=settings.openai_api_key), "gpt-4o-mini"

    async def generate_report(self, transcript: str) -> Dict[str, Any]:
        if not transcript:
            return {}

        prompt = SECTION_7_PROMPT.format(transcript=transcript)

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant that extracts structured data "
                            "from transcripts."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            
            report = json.loads(response.choices[0].message.content)
            return report
        except Exception as e:
            logger.error("generate_report_failed", error=str(e))
            return {}
