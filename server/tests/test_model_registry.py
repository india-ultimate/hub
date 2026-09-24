from django.db.models import Model
from django.db.models.fields.reverse_related import ForeignObjectRel
from django.test import SimpleTestCase

import server.models  # noqa: F401  # registers every model in the app
from server.core.models import Player, User

# A merge reassigns every row pointing at the account being absorbed. These
# counts fail the build when a relation is added, so merge.py gets taught
# about it instead of the rows being cascade-deleted.
INBOUND_USER_RELATIONS = 24
INBOUND_PLAYER_RELATIONS = 24


def inbound_relations(model: type[Model]) -> list[str]:
    return sorted(
        f"{rel.field.model._meta.label}.{rel.field.name}"
        for rel in model._meta.get_fields()
        if isinstance(rel, ForeignObjectRel)
    )


class TestInboundRelations(SimpleTestCase):
    def test_user_relation_count(self) -> None:
        relations = inbound_relations(User)
        self.assertEqual(len(relations), INBOUND_USER_RELATIONS, "\n".join(relations))

    def test_player_relation_count(self) -> None:
        relations = inbound_relations(Player)
        self.assertEqual(len(relations), INBOUND_PLAYER_RELATIONS, "\n".join(relations))

    def test_player_wrapped_is_registered(self) -> None:
        # Registered only via server/api.py before it was imported in
        # server/models, so introspection saw 23 relations or 24 by import order.
        self.assertIn("server.PlayerWrapped.player", inbound_relations(Player))
