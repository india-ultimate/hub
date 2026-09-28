from django.test import TestCase


class TestTheNumberBelongsToThePlayer(TestCase):
    def test_iu_id_is_on_player_and_legacy_number_is_hidden(self) -> None:
        from server.admin import SubscriptionAdmin
        from server.core.models import Player
        from server.subscription.models import Subscription
        from server.subscription.schema import SubscriptionSchema

        self.assertIn("iu_id", {f.name for f in Player._meta.fields})
        self.assertIn("subscription_number", {f.name for f in Subscription._meta.fields})
        self.assertNotIn("subscription_number", SubscriptionSchema.schema()["properties"])
        self.assertIn("subscription_number", SubscriptionAdmin.exclude)
