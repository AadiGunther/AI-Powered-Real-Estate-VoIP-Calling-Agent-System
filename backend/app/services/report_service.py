import json
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from openai import AsyncAzureOpenAI, AsyncOpenAI
from sqlalchemy import select

from app.config import settings
from app.database import async_session_maker
from app.models.call import Call

logger = logging.getLogger("voip.report_service")


class ReportService:
    """
    Generates post-call reports using LLM
    after the Twilio + Realtime call completes.
    """

    def __init__(self):
        if settings.azure_openai_api_key:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
            self.model = settings.azure_openai_deployment
        else:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = "gpt-4o"

    async def generate_report(
        self,
        call_sid: str,
        transcript: str,
        transcript_messages: list | None = None,
    ):
        if not transcript or not transcript.strip():
            logger.warning("empty_transcript_skipped", call_sid=call_sid)
            return

        try:
            # -----------------------------
            # 1. LLM Analysis
            # -----------------------------
            system_prompt = (
                "You are an expert real estate call analyst.\n\n"
                "Analyze the transcript of a phone call between an AI real estate assistant (Sophia) "
                "and a potential customer. EXTRACT SPECIFIC DETAILS.\n\n"
                "Return a STRICT JSON object with the following fields:\n"
                "- summary (string): A concise professional summary including name, specific requirements (BHK, location, budget), and next steps.\n"
                "- customer_intent (string): E.g., 'Buying 3BHK in Whitefield', 'Investment Inquiry'.\n"
                "- customer_name (string, optional): Extracted name.\n"
                "- customer_email (string, optional): Extracted email address.\n"
                "- interest_level (High | Medium | Low)\n"
                "- requirements (object): {\n"
                "    'budget': string or number,\n"
                "    'location': string,\n"
                "    'property_type': string,\n"
                "    'move_in_timeline': string\n"
                "  }\n"
                "- follow_up_required (boolean)\n"
                "- action_items (array of strings): Specific next steps (e.g., 'Send brochure to [email]', 'Schedule site visit').\n\n"
                "Do not include any extra text outside JSON."
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )

            raw_content = response.choices[0].message.content
            report_json = json.loads(raw_content)

            # -----------------------------
            # 2. Update SQL Call record & Get Phone Number
            # -----------------------------
            phone_number = "Unknown"
            async with async_session_maker() as db:
                stmt = select(Call).where(Call.call_sid == call_sid)
                result = await db.execute(stmt)
                call = result.scalar_one_or_none()

                if call:
                    # Update call record
                    call.transcript_summary = report_json.get("summary", "")[:500]
                    call.outcome = report_json.get("customer_intent", "unknown")[:50]
                    call.outcome_notes = (
                        f"Interest: {report_json.get('interest_level')}\n"
                        f"Follow-up required: {report_json.get('follow_up_required')}"
                    )
                    phone_number = call.from_number
                    
                    # Update Lead if exists
                    if call.lead_id:
                        from app.models.lead import Lead
                        stmt_lead = select(Lead).where(Lead.id == call.lead_id)
                        result_lead = await db.execute(stmt_lead)
                        lead = result_lead.scalar_one_or_none()
                        
                        if lead:
                            # Update summary and quality
                            lead.ai_summary = report_json.get("summary", "")
                            
                            interest = report_json.get("interest_level", "Low").lower()
                            if interest == "high":
                                lead.quality = "hot"
                            elif interest == "medium":
                                lead.quality = "warm"
                            
                            # Update contact details if extracted
                            extracted_email = report_json.get("customer_email")
                            if extracted_email and (not lead.email or lead.email == "unknown"):
                                lead.email = extracted_email
                                
                            extracted_name = report_json.get("customer_name")
                            if extracted_name and (not lead.name or lead.name == "Unknown Lead"):
                                lead.name = extracted_name
                            
                            # Update detailed preferences if available
                            reqs = report_json.get("requirements", {})
                            if reqs:
                                if reqs.get("budget"): lead.budget_max = reqs.get("budget") if isinstance(reqs.get("budget"), (int, float)) else None
                                if reqs.get("location"): lead.preferred_location = reqs.get("location")
                                if reqs.get("property_type"): lead.preferred_property_type = reqs.get("property_type")
                                
                                # Append requirements to notes for human readability
                                detailed_notes = f"\n--- AI extracted details ---\nBudget: {reqs.get('budget')}\nLocation: {reqs.get('location')}\nType: {reqs.get('property_type')}\nTimeline: {reqs.get('move_in_timeline')}"
                                lead.notes = (lead.notes or "") + detailed_notes

                    await db.commit()

            logger.info(
                "report_generated_successfully",
                call_sid=call_sid,
            )

        except Exception as e:
            logger.exception(
                "report_generation_failed",
                call_sid=call_sid,
                error=str(e),
            )
