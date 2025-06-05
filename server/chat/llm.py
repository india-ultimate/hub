import json
from collections.abc import Iterable
from typing import Any, NotRequired, TypedDict, TypeVar, cast

import groq
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from groq.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionFunctionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolParam,
    ChatCompletionUserMessageParam,
)

from server.core.models import Accreditation, CommentaryInfo, Player, Team, User
from server.membership.models import Membership
from server.season.models import Season
from server.series.models import Series, SeriesRegistration
from server.tournament.models import (
    Bracket,
    CrossPool,
    Match,
    MatchEvent,
    MatchStats,
    Pool,
    PositionPool,
    Registration,
    Tournament,
)

from .models import ChatMessage, ChatMessageType, ChatSession

T = TypeVar("T")


class ChatMessageDict(TypedDict):
    role: str
    content: str
    tool_call_id: NotRequired[str]


class ChatResponse(TypedDict):
    message: str
    tool_calls: NotRequired[list[dict[str, Any]]]


class ChatService:
    def __init__(self, groq_client: groq.Client, user: User) -> None:
        """Initialize the chat service with Groq client.

        Args:
            api_key: Optional API key. If not provided, uses GROQ_API_KEY from settings.
        """
        self.groq_client = groq_client
        self.model = settings.GROQ_MODEL
        self.temperature = settings.GROQ_TEMPERATURE
        self.max_tokens = settings.GROQ_MAX_TOKENS
        self.top_p = settings.GROQ_TOP_P
        self.user = user
        # System prompt to help Groq understand its role and capabilities
        self.system_prompt = """You are an AI assistant for India Ultimate, a sports organization. Your role is to help users get information about players, teams, tournaments, and other aspects of the organization. You should also provide analytical insights and statistics when requested.

User Context:
- Use the get_current_user tool to understand the logged-in user's context
- Consider their role, permissions, and associated data when providing responses
- Personalize responses based on their access level and relationships

Response Format:
- Always format responses in markdown when possible
- Use appropriate markdown elements:
  * Headers (#, ##, ###) for section titles
  * Lists (-, *) for enumerations
  * Bold (**) for emphasis
  * Tables for structured data
  * Code blocks (```) for JSON or code examples
  * Blockquotes (>) for important notes
- Keep responses clear, organized, and visually appealing
- Use markdown to highlight key information and improve readability

Key Data Structures and Concepts:

1. Players:
   - Basic info: name, age, gender, city, state
   - Membership: annual status, membership number, waiver info
   - Accreditation: WFDF accreditation level and validity
   - Commentary: player autobiographies and fun facts
   - Analytics: player participation trends, age distribution, gender ratios

2. Teams:
   - Basic info: name, category, state, city
   - Player counts and admin counts
   - Social media and image URLs
   - Analytics: team performance metrics, regional distribution, category trends

3. Seasons:
   - Annual membership periods
   - Membership fees (regular and sponsored)
   - Start and end dates
   - Analytics: membership growth, revenue trends, seasonal patterns

4. Series:
   - Tournament series information
   - Player limits and registration rules
   - Associated season and events
   - Analytics: participation rates, team performance across series

5. Tournaments:
   - Event details (title, dates, location, fees)
   - Registration windows and requirements
   - Team counts and volunteer information
   - Tournament structure:
     * Pools: Initial seeding and results
     * Cross Pools: Seeding information
     * Brackets: Initial and current seeding
     * Position Pools: Seeding and results
     * All tournaments happen first with pools, then cross pools(if needed), then brackets(Top4, Top 8 etc.) and position pools(Whenever odd number of teams left over from brackets) in parallel. Reseed happens after every round.
   - Matches:
     * Match details including scores, spirit scores, and field information
     * Match progression through tournament stages
     * Team performance in individual matches
     * Filtering by tournament, team, pool, bracket, cross pool, or position pool
   - Match Statistics:
     * Detailed match events (scores, drops, throwaways, blocks)
     * Line selections and gender ratios
     * Possession tracking
     * Player performance metrics
     * Match progression (first half, second half, completed)
   - Match Events:
     * Event types: Line Selection, Score, Drop, Throwaway, Block
     * Event modes: Offense, Defense
     * Player involvement in events
     * Event timing and sequence
     * Filtering by:
       - Team
       - Event type
       - Players involved
       - Scorer
       - Assist provider
       - Player who dropped
       - Player who threw away
       - Player who got the block/D
   - Analytics:
     * Performance metrics (goals scored/conceded)
     * Team rankings and progression
     * Spirit rankings
     * Registration trends
     * Volunteer participation
     * Match statistics and trends
     * Player performance analysis
     * Event analysis and patterns

6. Tournament Structure Data:
   - Seeding Data Format:
     * JSON where key is seed number (integer) and value is team ID (integer)
     * Example: {1: 123, 2: 456, 3: 789}

   - Results Data Format:
     * JSON where key is team ID and value is a dictionary containing:
       - "GA": Goals against (integer)
       - "GF": Goals for (integer)
       - "id": Team ID (integer)
       - "rank": Current rank (integer)
       - "wins": Number of wins (integer)
       - "draws": Number of draws (integer)
       - "losses": Number of losses (integer)
     * Example: {
         "123": {
             "GA": 10,
             "GF": 15,
             "id": 123,
             "rank": 1,
             "wins": 3,
             "draws": 0,
             "losses": 1
         }
       }

7. Registrations:
   - Tournament registrations (event, team, player)
   - Series registrations
   - Membership registrations
   - Analytics: registration patterns, participation rates

8. Matches:
   - Match details including:
     * Teams involved
     * Scores and spirit scores
     * Field information
     * Tournament stage
     * Match timing
     * Associated pool/bracket/cross pool/position pool
   - Match Statistics:
     * Current status (First Half, Second Half, Completed)
     * Team scores
     * Possession information
     * Line selection status
     * Gender ratios
     * Match events:
       - Line selections
       - Scores (with scorer and assist)
       - Drops
       - Throwaways
       - Blocks (with blocker/person who got the D)
   - Match Events:
     * Event details:
       - Type (Line Selection, Score, Drop, Throwaway, Block)
       - Mode (Offense, Defense)
       - Time and sequence
       - Team involved
       - Players involved
       - Specific player actions (scorer, assist, drop, throwaway, block)
     * Event filtering:
       - By team
       - By event type
       - By players involved
       - By specific player actions
   - Analytics:
     * Team performance in matches
     * Spirit score trends
     * Field utilization
     * Match timing patterns
     * Player performance metrics
     * Event analysis
     * Pattern recognition in events

9. Tournament Structure Filtering:
   - Pools:
     * Filter by tournament ID
     * Filter by specific pool ID
     * Get all pools
   - Brackets:
     * Filter by tournament ID
     * Filter by specific bracket ID
     * Get all brackets
   - Cross Pools:
     * Filter by tournament ID
     * Filter by specific cross pool ID
     * Get all cross pools
   - Position Pools:
     * Filter by tournament ID
     * Filter by specific position pool ID
     * Get all position pools

Analytics Capabilities:
1. Performance Analysis:
   - Team performance metrics
   - Player statistics
   - Tournament results and rankings
   - Spirit rankings and trends
   - Match-level analysis
   - Pool/bracket progression analysis
   - Player performance analysis
   - Event pattern analysis

2. Participation Analysis:
   - Registration trends
   - Membership growth
   - Volunteer engagement
   - Regional participation

3. Financial Analysis:
   - Membership revenue
   - Tournament fees
   - Sponsorship impact

4. Comparative Analysis:
   - Team performance across tournaments
   - Player participation across events
   - Regional participation patterns
   - Seasonal trends
   - Match performance patterns
   - Pool/bracket performance comparison
   - Player performance comparison
   - Event pattern comparison

Guidelines:
1. Always provide accurate and up-to-date information
2. Format responses in a clear, organized manner
3. Use appropriate tools to fetch specific information
4. Handle cases where data might not be available
5. Maintain context throughout the conversation
6. Be helpful and professional in tone
7. Provide analytical insights when requested
8. Use data to support conclusions and recommendations
9. Utilize filtering capabilities to provide focused information

Available Tools:
- Player information tools (stats, details, search, accreditation, commentary, membership)
- Team information tools (stats, details)
- Season information tools (all seasons, details)
- Series information tools (all series, details, registrations)
- Tournament information tools (all tournaments, details, search, registrations, structure)
- Tournament structure tools (pools, brackets, cross pools, position pools) with ID-based filtering
- Match information tools (details, search by tournament/team/pool/bracket)
- Match statistics tools (details, search by tournament/match)
- Match events tools (details, search by team/type/players/actions)
- User information tool (get_current_user)"""

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_user",
                    "description": "Get details of the currently logged in user including their role, permissions, and associated data",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_player_stats",
                    "description": "Get overall player statistics including total count, gender distribution, and age groups",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_team_stats",
                    "description": "Get team statistics including total count, distribution by category and state",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_player_details",
                    "description": "Get detailed information about a specific player",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "player_id": {
                                "type": "integer",
                                "description": "The ID of the player to get details for",
                            }
                        },
                        "required": ["player_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_players",
                    "description": "Search players by name, city, or team",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for player name, city, or team",
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_team_details",
                    "description": "Get detailed information about a specific team",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {
                                "type": "integer",
                                "description": "The ID of the team to get details for",
                            }
                        },
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_player_accreditation",
                    "description": "Get wfdf accreditation information for a specific player",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "player_id": {
                                "type": "integer",
                                "description": "The ID of the player to get accreditation for",
                            }
                        },
                        "required": ["player_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_player_commentary",
                    "description": "Get the autobiography of a specific player",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "player_id": {
                                "type": "integer",
                                "description": "The ID of the player to get their autobiography for",
                            }
                        },
                        "required": ["player_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_player_membership",
                    "description": "Get India Ultimate membership information for a specific player",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "player_id": {
                                "type": "integer",
                                "description": "The ID of the player to get India Ultimate membership details for",
                            }
                        },
                        "required": ["player_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_all_seasons",
                    "description": "Get information about all India Ultimate seasons",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_season_details",
                    "description": "Get detailed information about a specific India Ultimate season",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "season_id": {
                                "type": "integer",
                                "description": "The ID of the season to get details for",
                            }
                        },
                        "required": ["season_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_all_series",
                    "description": "Get information about all India Ultimate series",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_series_details",
                    "description": "Get detailed information about a specific India Ultimate series",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "series_id": {
                                "type": "integer",
                                "description": "The ID of the series to get details for",
                            }
                        },
                        "required": ["series_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_series_registrations",
                    "description": "Get series registrations filtered by series, team, or player",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "series_id": {
                                "type": "integer",
                                "description": "The ID of the series to get registrations for",
                            },
                            "team_id": {
                                "type": "integer",
                                "description": "The ID of the team to get registrations for",
                            },
                            "player_id": {
                                "type": "integer",
                                "description": "The ID of the player to get registrations for",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_all_tournaments",
                    "description": "Get information about all tournaments",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tournament_details",
                    "description": "Get detailed information about a specific tournament",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tournament_id": {
                                "type": "integer",
                                "description": "The ID of the tournament to get details for",
                            }
                        },
                        "required": ["tournament_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_tournaments",
                    "description": "Search tournaments by title, name, location, or type",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for tournament title, name, location, or type",
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tournament_registrations",
                    "description": "Get tournament registrations filtered by event, team, or player",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {
                                "type": "integer",
                                "description": "The ID of the event to get registrations for",
                            },
                            "team_id": {
                                "type": "integer",
                                "description": "The ID of the team to get registrations for",
                            },
                            "player_id": {
                                "type": "integer",
                                "description": "The ID of the player to get registrations for",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tournament_pools",
                    "description": "Get pools for a specific tournament or a specific pool by ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tournament_id": {
                                "type": "integer",
                                "description": "The ID of the tournament to get pools for",
                            },
                            "pool_id": {
                                "type": "integer",
                                "description": "The ID of the pool to get pools for",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tournament_brackets",
                    "description": "Get brackets for a specific tournament or a specific bracket by ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tournament_id": {
                                "type": "integer",
                                "description": "The ID of the tournament to get brackets for",
                            },
                            "bracket_id": {
                                "type": "integer",
                                "description": "The ID of the bracket to get brackets for",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tournament_cross_pools",
                    "description": "Get cross pools for a specific tournament or a specific cross pool by ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tournament_id": {
                                "type": "integer",
                                "description": "The ID of the tournament to get cross pools for",
                            },
                            "cross_pool_id": {
                                "type": "integer",
                                "description": "The ID of the cross pool to get cross pools for",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tournament_position_pools",
                    "description": "Get position pools for a specific tournament or a specific position pool by ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tournament_id": {
                                "type": "integer",
                                "description": "The ID of the tournament to get position pools for",
                            },
                            "position_pool_id": {
                                "type": "integer",
                                "description": "The ID of the position pool to get position pools for",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_match_details",
                    "description": "Get match details including scores, spirit scores, field information, and pool/bracket details",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "match_id": {
                                "type": "integer",
                                "description": "The ID of the match to get details for",
                            },
                            "tournament_id": {
                                "type": "integer",
                                "description": "The ID of the tournament to get matches for",
                            },
                            "team_id": {
                                "type": "integer",
                                "description": "The ID of the team to get matches for",
                            },
                            "pool_id": {
                                "type": "integer",
                                "description": "The ID of the pool to get matches for",
                            },
                            "bracket_id": {
                                "type": "integer",
                                "description": "The ID of the bracket to get matches for",
                            },
                            "cross_pool_id": {
                                "type": "integer",
                                "description": "The ID of the cross pool to get matches for",
                            },
                            "position_pool_id": {
                                "type": "integer",
                                "description": "The ID of the position pool to get matches for",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_match_stats",
                    "description": "Get detailed match statistics including events, scores, possession, and player performance",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "match_id": {
                                "type": "integer",
                                "description": "The ID of the match to get statistics for",
                            },
                            "tournament_id": {
                                "type": "integer",
                                "description": "The ID of the tournament to get match statistics for",
                            },
                            "stats_id": {
                                "type": "integer",
                                "description": "The ID of the match statistics to get",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_match_events",
                    "description": "Get match events filtered by team, type, players, or specific player actions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {
                                "type": "integer",
                                "description": "The ID of the team to get events for",
                            },
                            "event_type": {
                                "type": "string",
                                "description": "The type of event to filter by (Line Selection, Score, Drop, Throwaway, Block)",
                            },
                            "player_id": {
                                "type": "integer",
                                "description": "The ID of the player to get events for",
                            },
                            "scored_by_id": {
                                "type": "integer",
                                "description": "The ID of the player who scored",
                            },
                            "assisted_by_id": {
                                "type": "integer",
                                "description": "The ID of the player who provided the assist",
                            },
                            "drop_by_id": {
                                "type": "integer",
                                "description": "The ID of the player who dropped",
                            },
                            "throwaway_by_id": {
                                "type": "integer",
                                "description": "The ID of the player who threw away",
                            },
                            "block_by_id": {
                                "type": "integer",
                                "description": "The ID of the player who got the block/D",
                            },
                        },
                        "required": [],
                    },
                },
            },
        ]

    def get_or_create_session(self, user: User) -> ChatSession:
        """Get existing active session or create a new one for the user."""
        session = ChatSession.objects.filter(user=user).order_by("-created_at").first()
        if not session:
            session = ChatSession.objects.create(user=user)
        return session

    def process_message(self, user: User, message: str) -> str:
        """Process a user message and return the bot's response."""
        session = self.get_or_create_session(user)

        # Save user message
        ChatMessage.objects.create(session=session, message=message, type=ChatMessageType.USER)

        # Get conversation history
        conversation_history: list[
            ChatCompletionSystemMessageParam
            | ChatCompletionUserMessageParam
            | ChatCompletionAssistantMessageParam
            | ChatCompletionToolMessageParam
            | ChatCompletionFunctionMessageParam
        ] = [
            cast(
                ChatCompletionSystemMessageParam, {"role": "system", "content": self.system_prompt}
            )
        ]

        # Add user messages
        conversation_history.extend(
            [
                cast(
                    ChatCompletionUserMessageParam,
                    {"role": msg.get_type_display().lower(), "content": msg.message},
                )
                for msg in session.messages.all()
            ]
        )

        try:
            # Get response from Groq using configured model
            response = self.groq_client.chat.completions.create(
                messages=conversation_history,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                tools=cast(Iterable[ChatCompletionToolParam], self.tools),
                tool_choice="auto",
                stream=False,
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            if tool_calls:
                # Process tool calls
                conversation_history.append(
                    cast(
                        ChatCompletionAssistantMessageParam,
                        {
                            "role": "assistant",
                            "content": response_message.content or "",
                            "tool_calls": [
                                {
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.function.name,
                                        "arguments": tool_call.function.arguments,
                                    },
                                }
                                for tool_call in tool_calls
                            ],
                        },
                    )
                )

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    # Execute the appropriate function
                    function_response: dict[str, Any] = {}
                    if function_name == "get_player_stats":
                        function_response = self.get_player_stats()
                    elif function_name == "get_team_stats":
                        function_response = self.get_team_stats()
                    elif function_name == "get_player_details":
                        result = self.get_player_details(**function_args)
                        function_response = result if result is not None else {}
                    elif function_name == "search_players":
                        function_response = {"results": self.search_players(**function_args)}
                    elif function_name == "get_team_details":
                        result = self.get_team_details(**function_args)
                        function_response = result if result is not None else {}
                    elif function_name == "get_player_accreditation":
                        result = self.get_player_accreditation(**function_args)
                        function_response = result if result is not None else {}
                    elif function_name == "get_player_commentary":
                        result = self.get_player_commentary(**function_args)
                        function_response = result if result is not None else {}
                    elif function_name == "get_player_membership":
                        result = self.get_player_membership(**function_args)
                        function_response = result if result is not None else {}
                    elif function_name == "get_all_seasons":
                        function_response = {"seasons": self.get_all_seasons()}
                    elif function_name == "get_season_details":
                        result = self.get_season_details(**function_args)
                        function_response = result if result is not None else {}
                    elif function_name == "get_all_series":
                        function_response = {"series": self.get_all_series()}
                    elif function_name == "get_series_details":
                        result = self.get_series_details(**function_args)
                        function_response = result if result is not None else {}
                    elif function_name == "get_series_registrations":
                        function_response = {
                            "registrations": self.get_series_registrations(**function_args)
                        }
                    elif function_name == "get_all_tournaments":
                        function_response = {"tournaments": self.get_all_tournaments()}
                    elif function_name == "get_tournament_details":
                        result = self.get_tournament_details(**function_args)
                        function_response = result if result is not None else {}
                    elif function_name == "search_tournaments":
                        function_response = {"results": self.search_tournaments(**function_args)}
                    elif function_name == "get_tournament_registrations":
                        function_response = {
                            "registrations": self.get_tournament_registrations(**function_args)
                        }
                    elif function_name == "get_tournament_pools":
                        function_response = {"pools": self.get_tournament_pools(**function_args)}
                    elif function_name == "get_tournament_brackets":
                        function_response = {
                            "brackets": self.get_tournament_brackets(**function_args)
                        }
                    elif function_name == "get_tournament_cross_pools":
                        function_response = {
                            "cross_pools": self.get_tournament_cross_pools(**function_args)
                        }
                    elif function_name == "get_tournament_position_pools":
                        function_response = {
                            "position_pools": self.get_tournament_position_pools(**function_args)
                        }
                    elif function_name == "get_match_details":
                        function_response = {"matches": self.get_match_details(**function_args)}
                    elif function_name == "get_match_stats":
                        function_response = {"stats": self.get_match_stats(**function_args)}
                    elif function_name == "get_match_events":
                        function_response = {"events": self.get_match_events(**function_args)}
                    elif function_name == "get_current_user":
                        function_response = {"user": self.get_current_user()}

                    # Add tool response to conversation
                    conversation_history.append(
                        cast(
                            ChatCompletionToolMessageParam,
                            {
                                "role": "tool",
                                "content": json.dumps(function_response),
                                "tool_call_id": tool_call.id,
                            },
                        )
                    )

                # Get final response with tool results
                final_response = self.groq_client.chat.completions.create(
                    messages=conversation_history,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                    stream=False,
                )
                assistant_message = final_response.choices[0].message.content or ""
            else:
                assistant_message = response_message.content or ""

            # Save bot's response
            ChatMessage.objects.create(
                session=session,
                message=assistant_message,
                type=ChatMessageType.ASSISTANT,
                timestamp=timezone.now(),
            )

            return assistant_message

        except Exception as e:
            error_message = f"Error processing message: {e!s}"
            ChatMessage.objects.create(
                session=session,
                message=error_message,
                type=ChatMessageType.ASSISTANT,
                timestamp=timezone.now(),
            )
            return error_message

    def get_session_history(self, user: User) -> dict[str, Any]:
        """Get the chat history for a user's current session."""
        session = self.get_or_create_session(user)
        messages = session.messages.all()

        return {
            "session_id": session.id,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "messages": [
                {"type": msg.type, "message": msg.message, "timestamp": msg.timestamp}
                for msg in messages
            ],
        }

    def clear_session(self, user: User) -> bool:
        """Clear the current session for a user."""
        session = ChatSession.objects.filter(user=user).order_by("-created_at").first()
        if session:
            session.delete()
            return True
        return False

    # Tool Functions
    def get_player_stats(self) -> dict[str, Any]:
        """Get overall player statistics."""
        total_players = Player.objects.count()
        male_players = Player.objects.filter(gender="M").count()
        female_players = Player.objects.filter(gender="F").count()
        other_players = Player.objects.filter(gender="O").count()
        minor_players = Player.objects.filter(
            date_of_birth__gt=timezone.now().date() - relativedelta(years=18)
        ).count()

        return {
            "total_players": total_players,
            "gender_distribution": {
                "male": male_players,
                "female": female_players,
                "other": other_players,
            },
            "minor_players": minor_players,
            "major_players": total_players - minor_players,
        }

    def get_team_stats(self) -> dict[str, Any]:
        """Get team statistics."""
        total_teams = Team.objects.count()
        teams_by_category = Team.objects.values("category").annotate(count=Count("id"))
        teams_by_state = Team.objects.values("state_ut").annotate(count=Count("id"))

        return {
            "total_teams": total_teams,
            "teams_by_category": {item["category"]: item["count"] for item in teams_by_category},
            "teams_by_state": {
                item["state_ut"]: item["count"] for item in teams_by_state if item["state_ut"]
            },
        }

    def get_player_details(self, player_id: int) -> dict[str, Any] | None:
        """Get detailed information about a specific player."""
        try:
            player = Player.objects.get(id=player_id)
            return {
                "name": player.user.get_full_name(),
                "age": (timezone.now().date() - player.date_of_birth).days // 365,
                "gender": player.get_gender_display(),
                "city": player.city,
                "state": player.get_state_ut_display() if player.state_ut else None,
                "teams": [team.name for team in player.teams.all()],
                "occupation": player.get_occupation_display() if player.occupation else None,
                "educational_institution": player.educational_institution,
                "is_minor": player.is_minor,
                "is_sponsored": player.sponsored,
            }
        except Player.DoesNotExist:
            return None

    def search_players(self, query: str) -> list[dict[str, Any]]:
        """Search players by name, city, or team."""
        players = Player.objects.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(city__icontains=query)
            | Q(teams__name__icontains=query)
        ).distinct()

        return [
            {
                "id": player.id,
                "name": player.user.get_full_name(),
                "city": player.city,
                "teams": [team.name for team in player.teams.all()],
            }
            for player in players
        ]

    def get_team_details(self, team_id: int) -> dict[str, Any] | None:
        """Get detailed information about a specific team."""
        try:
            team = Team.objects.get(id=team_id)
            return {
                "name": team.name,
                "category": team.get_category_display(),
                "state": team.get_state_ut_display() if team.state_ut else None,
                "city": team.city,
                "player_count": team.players.count(),
                "admin_count": team.admins.count(),
                "facebook_url": team.facebook_url,
                "image_url": team.image_url,
            }
        except Team.DoesNotExist:
            return None

    def get_player_accreditation(self, player_id: int) -> dict[str, Any] | None:
        """Get wfdf accreditation information for a specific player."""
        try:
            player = Player.objects.get(id=player_id)
            accreditation = Accreditation.objects.filter(player=player).first()

            if not accreditation:
                return {
                    "has_accreditation": False,
                    "message": "No accreditation found for this player",
                }

            return {
                "has_accreditation": True,
                "is_valid": accreditation.is_valid,
                "level": accreditation.get_level_display(),
                "date": accreditation.date.isoformat(),
            }
        except Player.DoesNotExist:
            return None

    def get_player_commentary(self, player_id: int) -> dict[str, Any] | None:
        """Get the autobiography of a specific player."""
        try:
            player = Player.objects.get(id=player_id)
            commentary = CommentaryInfo.objects.filter(player=player).first()

            if not commentary:
                return {
                    "has_commentary": False,
                    "message": "No autobiography found for this player",
                }

            return {
                "has_commentary": True,
                "jersey_number": commentary.jersey_number,
                "ultimate_origin": commentary.ultimate_origin,
                "ultimate_attraction": commentary.ultimate_attraction,
                "ultimate_fav_role": commentary.ultimate_fav_role,
                "ultimate_fav_exp": commentary.ultimate_fav_exp,
                "interests": commentary.interests,
                "fun_fact": commentary.fun_fact,
            }
        except Player.DoesNotExist:
            return None

    def get_player_membership(self, player_id: int) -> dict[str, Any] | None:
        """Get India Ultimate membership information for a specific player."""
        try:
            player = Player.objects.get(id=player_id)
            membership = Membership.objects.filter(player=player).first()

            if not membership:
                return {
                    "has_membership": False,
                    "message": "No India Ultimate membership found for this player",
                }

            return {
                "has_membership": True,
                "membership_number": membership.membership_number,
                "is_annual": membership.is_annual,
                "start_date": membership.start_date.isoformat(),
                "end_date": membership.end_date.isoformat(),
                "is_active": membership.is_active,
                "waiver_valid": membership.waiver_valid,
                "waiver_signed_at": membership.waiver_signed_at.isoformat()
                if membership.waiver_signed_at
                else None,
                "waiver_signed_by": membership.waiver_signed_by.get_full_name()
                if membership.waiver_signed_by
                else None,
                "season": membership.season.name if membership.season else None,
                "event": membership.event.name if membership.event else None,
            }
        except Player.DoesNotExist:
            return None

    def get_all_seasons(self) -> list[dict[str, Any]]:
        """Get information about all India Ultimate seasons."""
        seasons = Season.objects.all().order_by("-start_date")
        return [
            {
                "id": season.id,
                "name": season.name,
                "start_date": season.start_date.isoformat(),
                "end_date": season.end_date.isoformat(),
                "annual_membership_amount": season.annual_membership_amount,
                "sponsored_annual_membership_amount": season.sponsored_annual_membership_amount,
            }
            for season in seasons
        ]

    def get_season_details(self, season_id: int) -> dict[str, Any] | None:
        """Get detailed information about a specific India Ultimate season."""
        try:
            season = Season.objects.get(id=season_id)
            return {
                "id": season.id,
                "name": season.name,
                "start_date": season.start_date.isoformat(),
                "end_date": season.end_date.isoformat(),
                "annual_membership_amount": season.annual_membership_amount,
                "sponsored_annual_membership_amount": season.sponsored_annual_membership_amount,
                "is_current": season.start_date <= timezone.now().date() <= season.end_date,
            }
        except Season.DoesNotExist:
            return None

    def get_all_series(self) -> list[dict[str, Any]]:
        """Get information about all India Ultimate series."""
        series = Series.objects.all().order_by("-start_date")
        return [
            {
                "id": series.id,
                "name": series.name,
                "slug": series.slug,
                "type": series.get_type_display(),
                "category": series.get_category_display(),
                "start_date": series.start_date.isoformat(),
                "end_date": series.end_date.isoformat(),
                "season": series.season.name if series.season else None,
                "series_roster_max_players": series.series_roster_max_players,
                "event_min_players_male": series.event_min_players_male,
                "event_min_players_female": series.event_min_players_female,
                "event_max_players_male": series.event_max_players_male,
                "event_max_players_female": series.event_max_players_female,
                "event_min_players_total": series.event_min_players_total,
                "event_max_players_total": series.event_max_players_total,
                "is_current": series.start_date <= timezone.now().date() <= series.end_date,
            }
            for series in series
        ]

    def get_series_details(self, series_id: int) -> dict[str, Any] | None:
        """Get detailed information about a specific India Ultimate series."""
        try:
            series = Series.objects.get(id=series_id)
            return {
                "id": series.id,
                "name": series.name,
                "slug": series.slug,
                "type": series.get_type_display(),
                "category": series.get_category_display(),
                "start_date": series.start_date.isoformat(),
                "end_date": series.end_date.isoformat(),
                "season": series.season.name if series.season else None,
                "series_roster_max_players": series.series_roster_max_players,
                "event_min_players_male": series.event_min_players_male,
                "event_min_players_female": series.event_min_players_female,
                "event_max_players_male": series.event_max_players_male,
                "event_max_players_female": series.event_max_players_female,
                "event_min_players_total": series.event_min_players_total,
                "event_max_players_total": series.event_max_players_total,
                "is_current": series.start_date <= timezone.now().date() <= series.end_date,
                "teams": [{"id": team.id, "name": team.name} for team in series.teams.all()],
            }
        except Series.DoesNotExist:
            return None

    def get_series_registrations(
        self, series_id: int | None = None, team_id: int | None = None, player_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Get series registrations filtered by series, team, or player."""
        registrations = SeriesRegistration.objects.all()

        if series_id:
            registrations = registrations.filter(series_id=series_id)
        if team_id:
            registrations = registrations.filter(team_id=team_id)
        if player_id:
            registrations = registrations.filter(player_id=player_id)

        return [
            {
                "id": reg.id,
                "series": {"id": reg.series.id, "name": reg.series.name},
                "team": {"id": reg.team.id, "name": reg.team.name},
                "player": {"id": reg.player.id, "name": reg.player.user.get_full_name()},
            }
            for reg in registrations
        ]

    def get_all_tournaments(self) -> list[dict[str, Any]]:
        """Get information about all tournaments."""
        tournaments = (
            Tournament.objects.all().select_related("event").order_by("-event__start_date")
        )
        return [
            {
                "id": tournament.id,
                "event_id": tournament.event.id,
                "title": tournament.event.title,
                "slug": tournament.event.slug,
                "type": tournament.event.get_type_display(),
                "start_date": tournament.event.start_date.isoformat(),
                "end_date": tournament.event.end_date.isoformat(),
                "location": tournament.event.location,
                "status": tournament.get_status_display(),
                "team_registration_start_date": tournament.event.team_registration_start_date.isoformat(),
                "team_registration_end_date": tournament.event.team_registration_end_date.isoformat(),
                "player_registration_start_date": tournament.event.player_registration_start_date.isoformat(),
                "player_registration_end_date": tournament.event.player_registration_end_date.isoformat(),
                "max_num_teams": tournament.event.max_num_teams,
                "team_fee": tournament.event.team_fee,
                "player_fee": tournament.event.player_fee,
                "partial_team_fee": tournament.event.partial_team_fee,
                "is_membership_needed": tournament.event.is_membership_needed,
                "tier": tournament.event.tier,
                "series": tournament.event.series.name if tournament.event.series else None,
                "team_count": tournament.teams.count(),
                "partial_team_count": tournament.partial_teams.count(),
                "volunteer_count": tournament.volunteers.count(),
                "is_current": tournament.event.start_date
                <= timezone.now().date()
                <= tournament.event.end_date,
            }
            for tournament in tournaments
        ]

    def get_tournament_details(self, tournament_id: int) -> dict[str, Any] | None:
        """Get detailed information about a specific tournament."""
        try:
            tournament = Tournament.objects.select_related("event").get(id=tournament_id)
            return {
                "id": tournament.id,
                "event_id": tournament.event.id,
                "title": tournament.event.title,
                "slug": tournament.event.slug,
                "type": tournament.event.get_type_display(),
                "start_date": tournament.event.start_date.isoformat(),
                "end_date": tournament.event.end_date.isoformat(),
                "location": tournament.event.location,
                "status": tournament.get_status_display(),
                "team_registration_start_date": tournament.event.team_registration_start_date.isoformat(),
                "team_registration_end_date": tournament.event.team_registration_end_date.isoformat(),
                "player_registration_start_date": tournament.event.player_registration_start_date.isoformat(),
                "player_registration_end_date": tournament.event.player_registration_end_date.isoformat(),
                "max_num_teams": tournament.event.max_num_teams,
                "team_fee": tournament.event.team_fee,
                "player_fee": tournament.event.player_fee,
                "partial_team_fee": tournament.event.partial_team_fee,
                "is_membership_needed": tournament.event.is_membership_needed,
                "tier": tournament.event.tier,
                "series": tournament.event.series.name if tournament.event.series else None,
                "teams": [{"id": team.id, "name": team.name} for team in tournament.teams.all()],
                "partial_teams": [
                    {"id": team.id, "name": team.name} for team in tournament.partial_teams.all()
                ],
                "volunteers": [
                    {"id": volunteer.id, "name": volunteer.get_full_name()}
                    for volunteer in tournament.volunteers.all()
                ],
                "rules": tournament.rules,
                "initial_seeding": tournament.initial_seeding,
                "current_seeding": tournament.current_seeding,
                "spirit_ranking": tournament.spirit_ranking,
                "use_uc_registrations": tournament.use_uc_registrations,
                "is_current": tournament.event.start_date
                <= timezone.now().date()
                <= tournament.event.end_date,
            }
        except Tournament.DoesNotExist:
            return None

    def search_tournaments(self, query: str) -> list[dict[str, Any]]:
        """Search tournaments by title, name, location, or type."""
        tournaments = (
            Tournament.objects.select_related("event")
            .filter(
                Q(event__title__icontains=query)
                | Q(event__location__icontains=query)
                | Q(event__type__icontains=query)
            )
            .order_by("-event__start_date")
        )

        return [
            {
                "id": tournament.id,
                "event_id": tournament.event.id,
                "title": tournament.event.title,
                "slug": tournament.event.slug,
                "type": tournament.event.get_type_display(),
                "start_date": tournament.event.start_date.isoformat(),
                "end_date": tournament.event.end_date.isoformat(),
                "location": tournament.event.location,
                "status": tournament.get_status_display(),
                "series": tournament.event.series.name if tournament.event.series else None,
                "team_count": tournament.teams.count(),
                "is_current": tournament.event.start_date
                <= timezone.now().date()
                <= tournament.event.end_date,
            }
            for tournament in tournaments
        ]

    def get_tournament_registrations(
        self, event_id: int | None = None, team_id: int | None = None, player_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Get tournament registrations filtered by event, team, or player."""
        registrations = Registration.objects.select_related("event", "team", "player").all()

        if event_id:
            registrations = registrations.filter(event_id=event_id)
        if team_id:
            registrations = registrations.filter(team_id=team_id)
        if player_id:
            registrations = registrations.filter(player_id=player_id)

        return [
            {
                "id": reg.id,
                "event": {
                    "id": reg.event.id,
                    "title": reg.event.title,
                    "type": reg.event.get_type_display(),
                },
                "team": {"id": reg.team.id, "name": reg.team.name},
                "player": {"id": reg.player.id, "name": reg.player.user.get_full_name()},
                "is_playing": reg.is_playing,
                "role": reg.get_role_display(),
                "performance_points": reg.points,
            }
            for reg in registrations
        ]

    def get_tournament_pools(
        self, tournament_id: int | None = None, pool_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Get pools for a specific tournament or a specific pool by ID.

        Initial seeding is stored as JSON where:
        - Key: Seed number (integer)
        - Value: Team ID (integer)

        Results are stored as JSON where:
        - Key: Team ID (integer)
        - Value: Dictionary containing:
            - "GA": Goals against (integer)
            - "GF": Goals for (integer)
            - "id": Team ID (integer)
            - "rank": Current rank (integer)
            - "wins": Number of wins (integer)
            - "draws": Number of draws (integer)
            - "losses": Number of losses (integer)
        """
        pools = Pool.objects.all()

        if tournament_id:
            pools = pools.filter(tournament_id=tournament_id)
        if pool_id:
            pools = pools.filter(id=pool_id)

        return [
            {
                "id": pool.id,
                "name": pool.name,
                "sequence_number": pool.sequence_number,
                "initial_seeding": pool.initial_seeding,  # {seed_number: team_id, ...}
                "results": pool.results,  # {team_id: {"GA": int, "GF": int, "id": int, "rank": int, "wins": int, "draws": int, "losses": int}, ...}
            }
            for pool in pools.order_by("sequence_number")
        ]

    def get_tournament_brackets(
        self, tournament_id: int | None = None, bracket_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Get brackets for a specific tournament or a specific bracket by ID.

        Initial and current seeding are stored as JSON where:
        - Key: Seed number (integer)
        - Value: Team ID (integer)
        """
        brackets = Bracket.objects.all()

        if tournament_id:
            brackets = brackets.filter(tournament_id=tournament_id)
        if bracket_id:
            brackets = brackets.filter(id=bracket_id)

        return [
            {
                "id": bracket.id,
                "name": bracket.name,
                "sequence_number": bracket.sequence_number,
                "initial_seeding": bracket.initial_seeding,  # {seed_number: team_id, ...}
                "current_seeding": bracket.current_seeding,  # {seed_number: team_id, ...}
            }
            for bracket in brackets.order_by("sequence_number")
        ]

    def get_tournament_cross_pools(
        self, tournament_id: int | None = None, cross_pool_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Get cross pools for a specific tournament or a specific cross pool by ID.

        Initial and current seeding are stored as JSON where:
        - Key: Seed number (integer)
        - Value: Team ID (integer)
        """
        cross_pools = CrossPool.objects.all()

        if tournament_id:
            cross_pools = cross_pools.filter(tournament_id=tournament_id)
        if cross_pool_id:
            cross_pools = cross_pools.filter(id=cross_pool_id)

        return [
            {
                "id": cross_pool.id,
                "initial_seeding": cross_pool.initial_seeding,  # {seed_number: team_id, ...}
                "current_seeding": cross_pool.current_seeding,  # {seed_number: team_id, ...}
            }
            for cross_pool in cross_pools
        ]

    def get_tournament_position_pools(
        self, tournament_id: int | None = None, position_pool_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Get position pools for a specific tournament or a specific position pool by ID.

        Initial seeding is stored as JSON where:
        - Key: Seed number (integer)
        - Value: Team ID (integer)

        Results are stored as JSON where:
        - Key: Team ID (integer)
        - Value: Dictionary containing:
            - "GA": Goals against (integer)
            - "GF": Goals for (integer)
            - "id": Team ID (integer)
            - "rank": Current rank (integer)
            - "wins": Number of wins (integer)
            - "draws": Number of draws (integer)
            - "losses": Number of losses (integer)
        """
        position_pools = PositionPool.objects.all()

        if tournament_id:
            position_pools = position_pools.filter(tournament_id=tournament_id)
        if position_pool_id:
            position_pools = position_pools.filter(id=position_pool_id)

        return [
            {
                "id": pool.id,
                "name": pool.name,
                "sequence_number": pool.sequence_number,
                "initial_seeding": pool.initial_seeding,  # {seed_number: team_id, ...}
                "results": pool.results,  # {team_id: {"GA": int, "GF": int, "id": int, "rank": int, "wins": int, "draws": int, "losses": int}, ...}
            }
            for pool in position_pools.order_by("sequence_number")
        ]

    def get_match_details(
        self,
        match_id: int | None = None,
        tournament_id: int | None = None,
        team_id: int | None = None,
        pool_id: int | None = None,
        bracket_id: int | None = None,
        cross_pool_id: int | None = None,
        position_pool_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get match details filtered by match ID, tournament, team, or pool/bracket/cross pool/position pool."""
        matches = Match.objects.select_related(
            "tournament",
            "team_1",
            "team_2",
            "field",
            "pool",
            "bracket",
            "cross_pool",
            "position_pool",
        ).all()

        if match_id:
            matches = matches.filter(id=match_id)
        if tournament_id:
            matches = matches.filter(tournament_id=tournament_id)
        if team_id:
            matches = matches.filter(Q(team_1_id=team_id) | Q(team_2_id=team_id))
        if pool_id:
            matches = matches.filter(pool_id=pool_id)
        if bracket_id:
            matches = matches.filter(bracket_id=bracket_id)
        if cross_pool_id:
            matches = matches.filter(cross_pool_id=cross_pool_id)
        if position_pool_id:
            matches = matches.filter(position_pool_id=position_pool_id)

        return [
            {
                "id": match.id,
                "tournament": {"id": match.tournament.id, "title": match.tournament.event.title},
                "team_1": {
                    "id": match.team_1.id,
                    "name": match.team_1.name,
                    "score": match.team_1_score,
                }
                if hasattr(match, "team_1") and match.team_1 is not None
                else None,
                "team_2": {
                    "id": match.team_2.id,
                    "name": match.team_2.name,
                    "score": match.team_2_score,
                }
                if hasattr(match, "team_2") and match.team_2 is not None
                else None,
                "field": {
                    "id": match.field.id,
                    "name": match.field.name,
                    "location": match.field.location,
                }
                if match.field
                else None,
                "spirit_score": match.spirit_score,
                "start_time": match.time.isoformat() if match.time else None,
                "duration_mins": match.duration_mins,
                "status": match.get_status_display(),
                "pool": {
                    "id": match.pool.id,
                    "name": match.pool.name,
                    "sequence_number": match.pool.sequence_number,
                    "initial_seeding": match.pool.initial_seeding,
                    "results": match.pool.results,
                }
                if match.pool
                else None,
                "bracket": {
                    "id": match.bracket.id,
                    "name": match.bracket.name,
                    "sequence_number": match.bracket.sequence_number,
                    "initial_seeding": match.bracket.initial_seeding,
                    "current_seeding": match.bracket.current_seeding,
                }
                if match.bracket
                else None,
                "cross_pool": {
                    "id": match.cross_pool.id,
                    "initial_seeding": match.cross_pool.initial_seeding,
                    "current_seeding": match.cross_pool.current_seeding,
                }
                if match.cross_pool
                else None,
                "position_pool": {
                    "id": match.position_pool.id,
                    "name": match.position_pool.name,
                    "sequence_number": match.position_pool.sequence_number,
                    "initial_seeding": match.position_pool.initial_seeding,
                    "results": match.position_pool.results,
                }
                if match.position_pool
                else None,
            }
            for match in matches
        ]

    def get_match_stats(
        self,
        match_id: int | None = None,
        tournament_id: int | None = None,
        stats_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get match statistics filtered by match ID, tournament, or stats ID."""
        stats = (
            MatchStats.objects.select_related(
                "match", "tournament", "initial_possession", "current_possession"
            )
            .prefetch_related("events", "events__players")
            .all()
        )

        if match_id:
            stats = stats.filter(match_id=match_id)
        if tournament_id:
            stats = stats.filter(tournament_id=tournament_id)
        if stats_id:
            stats = stats.filter(id=stats_id)

        return [
            {
                "id": stat.id,
                "match": {
                    "id": stat.match.id,
                    "name": stat.match.name,
                    "status": stat.match.get_status_display(),
                },
                "tournament": {"id": stat.tournament.id, "title": stat.tournament.event.title},
                "status": stat.get_status_display(),
                "score": {"team_1": stat.score_team_1, "team_2": stat.score_team_2},
                "possession": {
                    "initial": {
                        "id": stat.initial_possession.id,
                        "name": stat.initial_possession.name,
                    },
                    "current": {
                        "id": stat.current_possession.id,
                        "name": stat.current_possession.name,
                    },
                },
                "gender_ratio": {
                    "initial": stat.get_initial_ratio_display(),
                    "current": stat.get_current_ratio_display(),
                },
                "events": [
                    {
                        "id": event.id,
                        "type": event.get_type_display(),
                        "mode": event.get_started_on_display(),
                        "time": event.time.isoformat(),
                        "team": {"id": event.team.id, "name": event.team.name},
                        "players": [
                            {"id": player.id, "name": player.user.get_full_name()}
                            for player in event.players.all()
                        ],
                        "scored_by": {
                            "id": event.scored_by.id,
                            "name": event.scored_by.user.get_full_name(),
                        }
                        if event.scored_by
                        else None,
                        "assisted_by": {
                            "id": event.assisted_by.id,
                            "name": event.assisted_by.user.get_full_name(),
                        }
                        if event.assisted_by
                        else None,
                        "drop_by": {
                            "id": event.drop_by.id,
                            "name": event.drop_by.user.get_full_name(),
                        }
                        if event.drop_by
                        else None,
                        "throwaway_by": {
                            "id": event.throwaway_by.id,
                            "name": event.throwaway_by.user.get_full_name(),
                        }
                        if event.throwaway_by
                        else None,
                        "block_by": {
                            "id": event.block_by.id,
                            "name": event.block_by.user.get_full_name(),
                        }
                        if event.block_by
                        else None,
                    }
                    for event in stat.events.all()
                ],
            }
            for stat in stats
        ]

    def get_match_events(
        self,
        team_id: int | None = None,
        event_type: str | None = None,
        player_id: int | None = None,
        scored_by_id: int | None = None,
        assisted_by_id: int | None = None,
        drop_by_id: int | None = None,
        throwaway_by_id: int | None = None,
        block_by_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get match events filtered by team, type, players, or specific player actions."""
        events = (
            MatchEvent.objects.select_related(
                "stats",
                "stats__match",
                "stats__tournament",
                "team",
                "scored_by",
                "assisted_by",
                "drop_by",
                "throwaway_by",
                "block_by",
            )
            .prefetch_related("players")
            .all()
        )

        if team_id:
            events = events.filter(team_id=team_id)
        if event_type:
            events = events.filter(type=event_type)
        if player_id:
            events = events.filter(players__id=player_id)
        if scored_by_id:
            events = events.filter(scored_by_id=scored_by_id)
        if assisted_by_id:
            events = events.filter(assisted_by_id=assisted_by_id)
        if drop_by_id:
            events = events.filter(drop_by_id=drop_by_id)
        if throwaway_by_id:
            events = events.filter(throwaway_by_id=throwaway_by_id)
        if block_by_id:
            events = events.filter(block_by_id=block_by_id)

        return [
            {
                "id": event.id,
                "match": {
                    "id": event.stats.match.id,
                    "name": event.stats.match.name,
                    "status": event.stats.match.get_status_display(),
                },
                "tournament": {
                    "id": event.stats.tournament.id,
                    "title": event.stats.tournament.event.title,
                },
                "type": event.get_type_display(),
                "mode": event.get_started_on_display(),
                "time": event.time.isoformat(),
                "team": {"id": event.team.id, "name": event.team.name},
                "players": [
                    {"id": player.id, "name": player.user.get_full_name()}
                    for player in event.players.all()
                ],
                "scored_by": {
                    "id": event.scored_by.id,
                    "name": event.scored_by.user.get_full_name(),
                }
                if event.scored_by
                else None,
                "assisted_by": {
                    "id": event.assisted_by.id,
                    "name": event.assisted_by.user.get_full_name(),
                }
                if event.assisted_by
                else None,
                "drop_by": {"id": event.drop_by.id, "name": event.drop_by.user.get_full_name()}
                if event.drop_by
                else None,
                "throwaway_by": {
                    "id": event.throwaway_by.id,
                    "name": event.throwaway_by.user.get_full_name(),
                }
                if event.throwaway_by
                else None,
                "block_by": {"id": event.block_by.id, "name": event.block_by.user.get_full_name()}
                if event.block_by
                else None,
            }
            for event in events
        ]

    def get_current_user(self) -> dict[str, Any]:
        """Get details of the currently logged in user."""
        try:
            user = self.user
            player = Player.objects.filter(user=user).first()
            team_admin = Team.objects.filter(admins=user).first()

            return {
                "id": user.id,
                "name": user.get_full_name(),
                "email": user.email,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "roles": {
                    "is_player": bool(player),
                    "is_team_admin": bool(team_admin),
                },
                "player": {
                    "id": player.id,
                    "teams": [{"id": team.id, "name": team.name} for team in player.teams.all()],
                    "membership": {
                        "is_active": bool(
                            Membership.objects.filter(player=player, is_active=True).first()
                        )
                        if Membership.objects.filter(player=player).first()
                        else None,
                    },
                }
                if player is not None
                else None,
                "team_admin": {
                    "id": team_admin.id,
                    "name": team_admin.name,
                }
                if team_admin
                else None,
            }
        except Exception as e:
            return {"error": str(e)}
