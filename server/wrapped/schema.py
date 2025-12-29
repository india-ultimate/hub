from ninja import ModelSchema

from .models import PlayerWrapped


class PlayerWrappedSchema(ModelSchema):
    """
    Schema for player year-end wrapped data.

    JSON fields (most_scores_in_tournament, most_assists_in_tournament,
    most_blocks_in_tournament, teams_played_for, top_teammates_i_assisted,
    top_teammates_who_assisted_me) are automatically serialized as dict/list.
    """

    class Config:
        model = PlayerWrapped
        model_fields = "__all__"
