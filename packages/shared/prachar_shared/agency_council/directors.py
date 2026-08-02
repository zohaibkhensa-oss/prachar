"""The 9 AI Directors of the Agency Council.

Every Director owns exactly one responsibility. No Director may call
another Director. They work independently and return a DirectorOpinion.

Directors:
1. ChiefStrategyOfficer — positioning, objective, market opportunity
2. ChiefCreativeOfficer — creative concept, storytelling, visual language
3. ChiefMediaOfficer — channel mix, schedule, frequency, reach
4. ChiefPerformanceOfficer — ROI, CAC, CPA, CTR, conversions
5. ChiefBrandOfficer — brand consistency, tone, messaging, brand safety
6. ChiefFinancialOfficer — budget approval, return, risk, cost efficiency
7. ChiefComplianceOfficer — policies, legal, claims, regulatory
8. ChiefCustomerOfficer — audience fit, psychology, pain points, journey
9. ChiefAnalyticsOfficer — historical performance, memory, insights
"""
from __future__ import annotations

from typing import Any, ClassVar

from prachar_shared.ai_gateway import Tier

from .director_base import Director


# ─── 1. Chief Strategy Officer ──────────────────────────────────────────────


class ChiefStrategyOfficer(Director):
    """Owns: business positioning, campaign objective, market opportunity,
    brand differentiation, long-term growth. Never creates creative."""

    DIRECTOR_NAME: ClassVar[str] = "chief_strategy_officer"
    DIRECTOR_ROLE: ClassVar[str] = "Chief Strategy Officer"
    RESPONSIBILITY: ClassVar[str] = (
        "Business positioning, campaign objective, market opportunity, "
        "brand differentiation, long-term growth"
    )
    TIER: ClassVar[Tier] = Tier.large
    MAX_TOKENS: ClassVar[int] = 2048

    def _build_prompt(self, *, campaign_brief, round_number, previous_opinions, additional_context):
        brief_str = self._format_brief(campaign_brief)
        prev_str = self._format_previous_disagreements(previous_opinions)
        return (
            f"{self._safety_preamble()}\n"
            f"You are the CHIEF STRATEGY OFFICER. Your responsibility:\n"
            f"  Business positioning, campaign objective, market opportunity,\n"
            f"  brand differentiation, long-term growth.\n\n"
            f"You do NOT create creative concepts. You do NOT select channels.\n"
            f"You evaluate STRATEGY only.\n\n"
            f"CAMPAIGN BRIEF:\n{brief_str}\n\n"
            f"{prev_str}\n"
            f"{f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}\n\n"
            f"Review this campaign's STRATEGY. You MUST:\n"
            f"1. CITE SPECIFIC EVIDENCE — quote the exact section of the brief that\n"
            f"   supports each claim (put quoted text in evidence_cited).\n"
            f"2. CONSIDER AT LEAST 2 ALTERNATIVE strategic approaches before\n"
            f"   recommending one (list them in alternatives_considered with pros/cons).\n"
            f"3. QUANTIFY CONFIDENCE as a specific number 0.0-1.0 with reasoning\n"
            f"   (e.g., 0.72 because X is strong but Y is uncertain — NOT 'high').\n\n"
            f"Role-specific evaluation criteria:\n"
            f"- Strategic alignment: does the strategy map to the stated business goal?\n"
            f"- Market opportunity size: estimate the addressable opportunity.\n"
            f"- Competitive advantage sustainability: how defensible is the positioning?\n"
            f"- First-mover advantage assessment: is there a timing edge or is it me-too?\n"
            f"- What strategic risks exist?\n\n"
            f"Return your opinion with all fields. Be specific and cite evidence from the brief."
        )


# ─── 2. Chief Creative Officer ──────────────────────────────────────────────


class ChiefCreativeOfficer(Director):
    """Owns: creative concept, storytelling, visual language, emotion,
    brand identity, creative originality. Never selects channels."""

    DIRECTOR_NAME: ClassVar[str] = "chief_creative_officer"
    DIRECTOR_ROLE: ClassVar[str] = "Chief Creative Officer"
    RESPONSIBILITY: ClassVar[str] = (
        "Creative concept, storytelling, visual language, emotion, "
        "brand identity, creative originality"
    )
    TIER: ClassVar[Tier] = Tier.large
    MAX_TOKENS: ClassVar[int] = 2048

    def _build_prompt(self, *, campaign_brief, round_number, previous_opinions, additional_context):
        brief_str = self._format_brief(campaign_brief)
        prev_str = self._format_previous_disagreements(previous_opinions)
        return (
            f"{self._safety_preamble()}\n"
            f"You are the CHIEF CREATIVE OFFICER. Your responsibility:\n"
            f"  Creative concept, storytelling, visual language, emotion,\n"
            f"  brand identity, creative originality.\n\n"
            f"You do NOT select channels. You do NOT write media plans.\n"
            f"You evaluate CREATIVE only.\n\n"
            f"CAMPAIGN BRIEF:\n{brief_str}\n\n"
            f"{prev_str}\n"
            f"{f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}\n\n"
            f"Review this campaign's CREATIVE. You MUST:\n"
            f"1. CITE SPECIFIC EVIDENCE — quote the exact section of the brief that\n"
            f"   supports each claim (put quoted text in evidence_cited).\n"
            f"2. CONSIDER AT LEAST 2 ALTERNATIVE creative directions before\n"
            f"   recommending one (list them in alternatives_considered with pros/cons).\n"
            f"3. QUANTIFY CONFIDENCE as a specific number 0.0-1.0 with reasoning\n"
            f"   (e.g., 0.68 because the concept is strong but originality is unproven).\n\n"
            f"Role-specific evaluation criteria:\n"
            f"- Creative quality score (1-10): rate the concept's craft and execution.\n"
            f"- Brand voice consistency: does the creative match the brand's voice?\n"
            f"- Emotional resonance: will the target audience feel something?\n"
            f"- Originality assessment: is this fresh or derivative?\n"
            f"- Production complexity: how hard/costly is this to produce?\n\n"
            f"Return your opinion with all fields. Be specific and cite evidence from the brief."
        )


# ─── 3. Chief Media Officer ─────────────────────────────────────────────────


class ChiefMediaOfficer(Director):
    """Owns: channel mix, publishing schedule, frequency, reach,
    platform optimisation. Never writes copy."""

    DIRECTOR_NAME: ClassVar[str] = "chief_media_officer"
    DIRECTOR_ROLE: ClassVar[str] = "Chief Media Officer"
    RESPONSIBILITY: ClassVar[str] = (
        "Channel mix, publishing schedule, frequency, reach, "
        "platform optimisation"
    )
    TIER: ClassVar[Tier] = Tier.large
    MAX_TOKENS: ClassVar[int] = 1536

    def _build_prompt(self, *, campaign_brief, round_number, previous_opinions, additional_context):
        brief_str = self._format_brief(campaign_brief)
        prev_str = self._format_previous_disagreements(previous_opinions)
        return (
            f"{self._safety_preamble()}\n"
            f"You are the CHIEF MEDIA OFFICER. Your responsibility:\n"
            f"  Channel mix, publishing schedule, frequency, reach,\n"
            f"  platform optimisation.\n\n"
            f"You do NOT write copy. You do NOT create creative.\n"
            f"You evaluate MEDIA only.\n\n"
            f"CAMPAIGN BRIEF:\n{brief_str}\n\n"
            f"{prev_str}\n"
            f"{f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}\n\n"
            f"Review this campaign's MEDIA PLAN. You MUST:\n"
            f"1. CITE SPECIFIC EVIDENCE — quote the exact section of the brief that\n"
            f"   supports each claim (put quoted text in evidence_cited).\n"
            f"2. CONSIDER AT LEAST 2 ALTERNATIVE channel mixes before recommending\n"
            f"   one (list them in alternatives_considered with pros/cons).\n"
            f"3. QUANTIFY CONFIDENCE as a specific number 0.0-1.0 with reasoning\n"
            f"   (e.g., 0.71 because reach is solid but frequency may cause fatigue).\n\n"
            f"Role-specific evaluation criteria:\n"
            f"- Channel mix efficiency: is spend allocated to the right channels?\n"
            f"- Reach vs frequency balance: is the trade-off optimal?\n"
            f"- Cross-channel synergy: do the channels reinforce each other?\n"
            f"- Audience overlap analysis: how much audience duplication exists?\n"
            f"- Is each channel being used to its strengths?\n\n"
            f"Return your opinion with all fields. Be specific and cite evidence from the brief."
        )


# ─── 4. Chief Performance Officer ───────────────────────────────────────────


class ChiefPerformanceOfficer(Director):
    """Owns: ROI, CAC, CPA, CTR, expected conversions, growth modelling.
    Never creates media."""

    DIRECTOR_NAME: ClassVar[str] = "chief_performance_officer"
    DIRECTOR_ROLE: ClassVar[str] = "Chief Performance Officer"
    RESPONSIBILITY: ClassVar[str] = (
        "ROI, CAC, CPA, CTR, expected conversions, growth modelling"
    )
    TIER: ClassVar[Tier] = Tier.large
    MAX_TOKENS: ClassVar[int] = 1536

    def _build_prompt(self, *, campaign_brief, round_number, previous_opinions, additional_context):
        brief_str = self._format_brief(campaign_brief)
        prev_str = self._format_previous_disagreements(previous_opinions)
        return (
            f"{self._safety_preamble()}\n"
            f"You are the CHIEF PERFORMANCE OFFICER. Your responsibility:\n"
            f"  ROI, CAC, CPA, CTR, expected conversions, growth modelling.\n\n"
            f"You do NOT create media plans. You do NOT select channels.\n"
            f"You evaluate PERFORMANCE only.\n\n"
            f"CAMPAIGN BRIEF:\n{brief_str}\n\n"
            f"{prev_str}\n"
            f"{f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}\n\n"
            f"Review this campaign's expected PERFORMANCE. You MUST:\n"
            f"1. CITE SPECIFIC EVIDENCE — quote the exact section of the brief that\n"
            f"   supports each claim (put quoted text in evidence_cited).\n"
            f"2. CONSIDER AT LEAST 2 ALTERNATIVE performance strategies before\n"
            f"   recommending one (list them in alternatives_considered with pros/cons).\n"
            f"3. QUANTIFY CONFIDENCE as a specific number 0.0-1.0 with reasoning\n"
            f"   (e.g., 0.63 because ROI is plausible but CAC lacks benchmark data).\n\n"
            f"Role-specific evaluation criteria:\n"
            f"- ROI projection: is the expected return realistic for the budget?\n"
            f"- CAC estimate: is the projected customer acquisition cost within norms?\n"
            f"- Conversion funnel analysis: where are the funnel drop-off risks?\n"
            f"- Attribution model recommendation: which model fits this campaign?\n"
            f"- Is the growth model sound?\n\n"
            f"Return your opinion with all fields. Be specific and cite evidence from the brief."
        )


# ─── 5. Chief Brand Officer ─────────────────────────────────────────────────


class ChiefBrandOfficer(Director):
    """Owns: brand consistency, tone, messaging, colours, typography, brand safety."""

    DIRECTOR_NAME: ClassVar[str] = "chief_brand_officer"
    DIRECTOR_ROLE: ClassVar[str] = "Chief Brand Officer"
    RESPONSIBILITY: ClassVar[str] = (
        "Brand consistency, tone, messaging, colours, typography, brand safety"
    )
    TIER: ClassVar[Tier] = Tier.large
    MAX_TOKENS: ClassVar[int] = 1536

    def _build_prompt(self, *, campaign_brief, round_number, previous_opinions, additional_context):
        brief_str = self._format_brief(campaign_brief)
        prev_str = self._format_previous_disagreements(previous_opinions)
        return (
            f"{self._safety_preamble()}\n"
            f"You are the CHIEF BRAND OFFICER. Your responsibility:\n"
            f"  Brand consistency, tone, messaging, colours, typography, brand safety.\n\n"
            f"You evaluate BRAND CONSISTENCY only.\n\n"
            f"CAMPAIGN BRIEF:\n{brief_str}\n\n"
            f"{prev_str}\n"
            f"{f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}\n\n"
            f"Review this campaign's BRAND CONSISTENCY. You MUST:\n"
            f"1. CITE SPECIFIC EVIDENCE — quote the exact section of the brief that\n"
            f"   supports each claim (put quoted text in evidence_cited).\n"
            f"2. CONSIDER AT LEAST 2 ALTERNATIVE brand messaging approaches before\n"
            f"   recommending one (list them in alternatives_considered with pros/cons).\n"
            f"3. QUANTIFY CONFIDENCE as a specific number 0.0-1.0 with reasoning\n"
            f"   (e.g., 0.77 because tone is on-brand but messaging hierarchy is unclear).\n\n"
            f"Role-specific evaluation criteria:\n"
            f"- Brand safety assessment: are there any brand safety concerns?\n"
            f"- Tone consistency: is the tone consistent with the brand voice?\n"
            f"- Messaging hierarchy: is the primary message clear and supported?\n"
            f"- Brand equity impact: does this strengthen or dilute the brand?\n"
            f"- Are colours and typography aligned with brand guidelines?\n\n"
            f"Return your opinion with all fields. Be specific and cite evidence from the brief."
        )


# ─── 6. Chief Financial Officer ─────────────────────────────────────────────


class ChiefFinancialOfficer(Director):
    """Owns: budget approval, expected return, risk, cost efficiency, financial viability."""

    DIRECTOR_NAME: ClassVar[str] = "chief_financial_officer"
    DIRECTOR_ROLE: ClassVar[str] = "Chief Financial Officer"
    RESPONSIBILITY: ClassVar[str] = (
        "Budget approval, expected return, risk, cost efficiency, financial viability"
    )
    TIER: ClassVar[Tier] = Tier.large
    MAX_TOKENS: ClassVar[int] = 1536

    def _build_prompt(self, *, campaign_brief, round_number, previous_opinions, additional_context):
        brief_str = self._format_brief(campaign_brief)
        prev_str = self._format_previous_disagreements(previous_opinions)
        return (
            f"{self._safety_preamble()}\n"
            f"You are the CHIEF FINANCIAL OFFICER. Your responsibility:\n"
            f"  Budget approval, expected return, risk, cost efficiency, financial viability.\n\n"
            f"You evaluate FINANCIAL VIABILITY only.\n\n"
            f"CAMPAIGN BRIEF:\n{brief_str}\n\n"
            f"{prev_str}\n"
            f"{f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}\n\n"
            f"Review this campaign's FINANCIAL VIABILITY. You MUST:\n"
            f"1. CITE SPECIFIC EVIDENCE — quote the exact section of the brief that\n"
            f"   supports each claim (put quoted text in evidence_cited).\n"
            f"2. CONSIDER AT LEAST 2 ALTERNATIVE budget allocations before\n"
            f"   recommending one (list them in alternatives_considered with pros/cons).\n"
            f"3. QUANTIFY CONFIDENCE as a specific number 0.0-1.0 with reasoning\n"
            f"   (e.g., 0.59 because the budget is tight and ROI assumptions are aggressive).\n\n"
            f"Role-specific evaluation criteria:\n"
            f"- Budget efficiency ratio: is spend vs expected return well-balanced?\n"
            f"- Cost per acquisition projection: is the CPA estimate realistic?\n"
            f"- Marginal ROI analysis: does incremental spend yield diminishing returns?\n"
            f"- Financial risk assessment: what financial risks exist?\n"
            f"- Should the budget be approved, reduced, or rejected?\n\n"
            f"Return your opinion with all fields. Be specific and cite evidence from the brief."
        )


# ─── 7. Chief Compliance Officer ────────────────────────────────────────────


class ChiefComplianceOfficer(Director):
    """Owns: advertising policies, legal risk, sensitive industries,
    claims review, regulatory compliance, platform compliance."""

    DIRECTOR_NAME: ClassVar[str] = "chief_compliance_officer"
    DIRECTOR_ROLE: ClassVar[str] = "Chief Compliance Officer"
    RESPONSIBILITY: ClassVar[str] = (
        "Advertising policies, legal risk, sensitive industries, claims review, "
        "regulatory compliance, platform compliance"
    )
    TIER: ClassVar[Tier] = Tier.large
    MAX_TOKENS: ClassVar[int] = 1536
    TEMPERATURE: ClassVar[float] = 0.2  # Lower temperature for compliance

    def _build_prompt(self, *, campaign_brief, round_number, previous_opinions, additional_context):
        brief_str = self._format_brief(campaign_brief)
        prev_str = self._format_previous_disagreements(previous_opinions)
        return (
            f"{self._safety_preamble()}\n"
            f"You are the CHIEF COMPLIANCE OFFICER. Your responsibility:\n"
            f"  Advertising policies, legal risk, sensitive industries, claims review,\n"
            f"  regulatory compliance, platform compliance.\n\n"
            f"You evaluate COMPLIANCE only. You are conservative by default.\n"
            f"If there is ANY compliance risk, you must NOT approve.\n\n"
            f"CAMPAIGN BRIEF:\n{brief_str}\n\n"
            f"{prev_str}\n"
            f"{f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}\n\n"
            f"Review this campaign's COMPLIANCE. You MUST:\n"
            f"1. CITE SPECIFIC EVIDENCE — quote the exact section of the brief that\n"
            f"   supports each claim (put quoted text in evidence_cited).\n"
            f"2. CONSIDER AT LEAST 2 ALTERNATIVE compliance mitigation approaches\n"
            f"   before recommending one (list them in alternatives_considered).\n"
            f"3. QUANTIFY CONFIDENCE as a specific number 0.0-1.0 with reasoning\n"
            f"   (e.g., 0.85 because no prohibited claims detected, but industry is sensitive).\n\n"
            f"Role-specific evaluation criteria:\n"
            f"- Regulatory compliance check: are there regulatory risks?\n"
            f"- Claims verification: are there prohibited claims (guaranteed, medical, financial)?\n"
            f"- Platform policy alignment: will any platform policies be violated?\n"
            f"- Data privacy assessment: are there data collection or privacy concerns?\n"
            f"- Is the industry sensitive (alcohol, gambling, health, finance)?\n\n"
            f"Return your opinion with all fields. Be conservative. Cite evidence from the brief."
        )


# ─── 8. Chief Customer Officer ──────────────────────────────────────────────


class ChiefCustomerOfficer(Director):
    """Owns: audience fit, customer psychology, pain points, buying behaviour, user journey."""

    DIRECTOR_NAME: ClassVar[str] = "chief_customer_officer"
    DIRECTOR_ROLE: ClassVar[str] = "Chief Customer Officer"
    RESPONSIBILITY: ClassVar[str] = (
        "Audience fit, customer psychology, pain points, buying behaviour, user journey"
    )
    TIER: ClassVar[Tier] = Tier.large
    MAX_TOKENS: ClassVar[int] = 1536

    def _build_prompt(self, *, campaign_brief, round_number, previous_opinions, additional_context):
        brief_str = self._format_brief(campaign_brief)
        prev_str = self._format_previous_disagreements(previous_opinions)
        return (
            f"{self._safety_preamble()}\n"
            f"You are the CHIEF CUSTOMER OFFICER. Your responsibility:\n"
            f"  Audience fit, customer psychology, pain points, buying behaviour, user journey.\n\n"
            f"You evaluate CUSTOMER FIT only.\n\n"
            f"CAMPAIGN BRIEF:\n{brief_str}\n\n"
            f"{prev_str}\n"
            f"{f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}\n\n"
            f"Review this campaign's CUSTOMER FIT. You MUST:\n"
            f"1. CITE SPECIFIC EVIDENCE — quote the exact section of the brief that\n"
            f"   supports each claim (put quoted text in evidence_cited).\n"
            f"2. CONSIDER AT LEAST 2 ALTERNATIVE customer engagement approaches\n"
            f"   before recommending one (list them in alternatives_considered with pros/cons).\n"
            f"3. QUANTIFY CONFIDENCE as a specific number 0.0-1.0 with reasoning\n"
            f"   (e.g., 0.74 because pain points are addressed but journey has friction).\n\n"
            f"Role-specific evaluation criteria:\n"
            f"- Customer benefit clarity: is the value proposition clear to the customer?\n"
            f"- Pain point resolution score (1-10): how well does this solve real pain?\n"
            f"- Experience quality assessment: is the ad-to-conversion journey smooth?\n"
            f"- Feedback loop recommendation: how should post-launch feedback be collected?\n"
            f"- Is the customer psychology understood correctly?\n\n"
            f"Return your opinion with all fields. Be specific and cite evidence from the brief."
        )


# ─── 9. Chief Analytics Officer ─────────────────────────────────────────────


class ChiefAnalyticsOfficer(Director):
    """Owns: historical performance, previous campaigns, business memory,
    insights, recommendations."""

    DIRECTOR_NAME: ClassVar[str] = "chief_analytics_officer"
    DIRECTOR_ROLE: ClassVar[str] = "Chief Analytics Officer"
    RESPONSIBILITY: ClassVar[str] = (
        "Historical performance, previous campaigns, business memory, "
        "insights, recommendations"
    )
    TIER: ClassVar[Tier] = Tier.large
    MAX_TOKENS: ClassVar[int] = 1536

    def _build_prompt(self, *, campaign_brief, round_number, previous_opinions, additional_context):
        brief_str = self._format_brief(campaign_brief)
        prev_str = self._format_previous_disagreements(previous_opinions)
        # The additional_context for Analytics contains business memory
        memory_str = additional_context if additional_context else "No historical data available."
        return (
            f"{self._safety_preamble()}\n"
            f"You are the CHIEF ANALYTICS OFFICER. Your responsibility:\n"
            f"  Historical performance, previous campaigns, business memory,\n"
            f"  insights, recommendations.\n\n"
            f"You evaluate based on HISTORICAL DATA only.\n"
            f"If no historical data is available, say so explicitly.\n\n"
            f"CAMPAIGN BRIEF:\n{brief_str}\n\n"
            f"BUSINESS MEMORY / HISTORICAL DATA:\n{memory_str}\n\n"
            f"{prev_str}\n\n"
            f"Review this campaign based on HISTORICAL PERFORMANCE. You MUST:\n"
            f"1. CITE SPECIFIC EVIDENCE — quote the exact section of the brief or\n"
            f"   historical data that supports each claim (put in evidence_cited).\n"
            f"2. CONSIDER AT LEAST 2 ALTERNATIVE measurement approaches before\n"
            f"   recommending one (list them in alternatives_considered with pros/cons).\n"
            f"3. QUANTIFY CONFIDENCE as a specific number 0.0-1.0 with reasoning\n"
            f"   (e.g., 0.55 because no historical baseline exists for this campaign type).\n\n"
            f"Role-specific evaluation criteria:\n"
            f"- Measurability assessment: can the campaign outcomes be reliably measured?\n"
            f"- KPI definition quality: are the KPIs well-defined and actionable?\n"
            f"- Data collection plan: is there a clear plan for gathering performance data?\n"
            f"- Baseline establishment: is there a historical baseline to compare against?\n"
            f"- What patterns from historical data are relevant?\n\n"
            f"Return your opinion with all fields. Cite evidence from the historical data."
        )


# ─── Registry of all directors ──────────────────────────────────────────────


ALL_DIRECTORS: list[type[Director]] = [
    ChiefStrategyOfficer,
    ChiefCreativeOfficer,
    ChiefMediaOfficer,
    ChiefPerformanceOfficer,
    ChiefBrandOfficer,
    ChiefFinancialOfficer,
    ChiefComplianceOfficer,
    ChiefCustomerOfficer,
    ChiefAnalyticsOfficer,
]

DIRECTOR_NAMES: list[str] = [d.DIRECTOR_NAME for d in ALL_DIRECTORS]
