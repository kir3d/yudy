from app.repositories.analytics import AnalyticsRepository

EVENT_PROPERTIES = {
    "registration_completed": set(),
    "legal_accepted": {"documents"},
    "onboarding_completed": set(),
    "risk_profile_completed": {"questionnaire_version"},
    "asset_viewed": {"asset_id"},
    "asset_liked": {"asset_id"},
    "asset_disliked": {"asset_id"},
    "asset_saved": {"asset_id"},
    "asset_unsaved": {"asset_id"},
    "buy_clicked": {"asset_id", "tokenized_asset_id", "interaction_id", "provider", "demo"},
    "learn_article_opened": {"article_id", "slug"},
}


class AnalyticsService:
    """Internal events join the caller's transaction; no separate commit or transport."""

    def __init__(self, session):
        self.repository = AnalyticsRepository(session)

    def record(self, event_name, user_id=None, **properties):
        if event_name not in EVENT_PROPERTIES or set(properties) != EVENT_PROPERTIES[event_name]:
            raise ValueError("Invalid internal analytics event or properties")
        self.repository.add(event_name, user_id, properties)
