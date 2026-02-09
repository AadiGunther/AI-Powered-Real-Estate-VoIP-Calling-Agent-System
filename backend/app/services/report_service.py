import json
import logging
from datetime import datetime, timezone

from openai import AsyncAzureOpenAI, AsyncOpenAI
from sqlalchemy import select

from app.config import settings
from app.database import get_mongodb, async_session_maker
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

            # -----------------------------
            # 3. Save to MongoDB (Transcripts, Reports, Summaries)
            # -----------------------------
            mongo = get_mongodb()

            # A. Save raw transcript
            transcript_doc = {
                "call_sid": call_sid,
                "messages": transcript_messages or [],
                "full_text": transcript,
                "created_at": datetime.now(timezone.utc),
            }
            transcript_result = await mongo.transcripts.insert_one(transcript_doc)
            transcript_id = str(transcript_result.inserted_id)

            # Update SQL with the ID (second pass? efficient enough)
            async with async_session_maker() as db:
                 stmt = select(Call).where(Call.call_sid == call_sid)
                 result = await db.execute(stmt)
                 call = result.scalar_one_or_none()
                 if call:
                     call.transcript_id = transcript_id
                     await db.commit()

            # B. Save Analysis/Report
            report_doc = {
                "call_sid": call_sid,
                "transcript_id": transcript_id,
                "summary": report_json.get("summary", ""),
                "analysis": report_json,
                "created_at": datetime.now(timezone.utc),
            }
            await mongo.reports.insert_one(report_doc)

            # C. Save Conversation Summary (for Frontend/API)
            try:
                from app.models.conversation_summary import ConversationSummary
                
                # Extract fields safely
                summary_data = {
                    "call_sid": call_sid,
                    "summary": report_json.get("summary", "")[:500],
                    "customer_name": report_json.get("customer_name"), # LLM might not give this
                    "phone_number": phone_number,
                    "preferred_language": report_json.get("preferred_language"),
                    "requirements": report_json.get("requirements", {}),
                    "properties_discussed": report_json.get("properties_discussed", []),
                    "lead_quality": report_json.get("lead_quality", "cold"),
                    "key_points": report_json.get("key_points", []),
                    "next_steps": report_json.get("action_items", []) if isinstance(report_json.get("action_items"), str) else (report_json.get("next_steps") or (report_json.get("action_items")[0] if report_json.get("action_items") else None)),
                    "created_at": datetime.now(timezone.utc)
                }
                
                # Sanitize next_steps if it came from action_items array
                if not summary_data["next_steps"] and report_json.get("action_items"):
                     summary_data["next_steps"] = "; ".join(report_json.get("action_items"))

                conv_summary = ConversationSummary(**summary_data)
                await mongo.conversation_summaries.insert_one(conv_summary.model_dump())

            except Exception as e:
                logger.error("conversation_summary_save_failed", error=str(e), call_sid=call_sid)

            logger.info(
                "report_generated_successfully",
                call_sid=call_sid,
                report_id=transcript_id, # Using transcript ID as primary ref
            )

        except Exception as e:
            logger.exception(
                "report_generation_failed",
                call_sid=call_sid,
                error=str(e),
            )
