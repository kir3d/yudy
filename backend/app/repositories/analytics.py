from app.models.analytics import AnalyticsEvent


class AnalyticsRepository:
    def __init__(self, session):
        self.session = session

    def add(self, event_name, user_id, properties):
        self.session.add(
            AnalyticsEvent(event_name=event_name, user_id=user_id, properties=properties)
        )
