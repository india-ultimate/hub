from ninja import ModelSchema

from server.core.models import Player

from .models import PlayerWrapped


class PlayerWrappedSchema(ModelSchema):
    """
    Schema for player year-end wrapped data.

    JSON fields (most_scores_in_tournament, most_assists_in_tournament,
    most_blocks_in_tournament, teams_played_for, top_teammates_i_assisted,
    top_teammates_who_assisted_me) are automatically serialized as dict/list.
    """

    teammate_slugs: dict[int, str]

    @staticmethod
    def resolve_teammate_slugs(wrapped: PlayerWrapped) -> dict[int, str]:
        ids = {
            row["player_id"]
            for rows in (wrapped.top_teammates_i_assisted, wrapped.top_teammates_who_assisted_me)
            for row in rows or []
        }
        rows = Player.objects.filter(id__in=ids).values_list("id", "slug")
        return {id_: slug for id_, slug in rows if slug}

    class Meta:
        model = PlayerWrapped
        fields = "__all__"
