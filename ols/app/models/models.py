"""Data models representing payloads for REST API calls."""

import json
from collections import OrderedDict
from typing import Any, Optional, Self, Union

from langchain.llms.base import LLM
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, field_validator, model_validator
from pydantic.dataclasses import dataclass

from ols.constants import MEDIA_TYPE_JSON, MEDIA_TYPE_TEXT
from ols.customize import prompts
from ols.utils import suid


class Attachment(BaseModel):
    """Model representing an attachment that can be send from UI as part of query.

    List of attachments can be optional part of 'query' request.

    Attributes:
        attachment_type: The attachment type, like "log", "configuration" etc.
        content_type: The content type as defined in MIME standard
        content: The actual attachment content

    YAML attachments with **kind** and **metadata/name** attributes will
    be handled as resources with specified name:
    ```
    kind: Pod
    metadata:
        name: private-reg
    ```
    """

    attachment_type: str
    content_type: str
    content: str

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "attachment_type": "log",
                    "content_type": "text/plain",
                    "content": "this is attachment",
                },
                {
                    "attachment_type": "configuration",
                    "content_type": "application/yaml",
                    "content": "kind: Pod\n metadata:\n name:    private-reg",
                },
                {
                    "attachment_type": "configuration",
                    "content_type": "application/yaml",
                    "content": "foo: bar",
                },
            ]
        }
    }


class LLMRequest(BaseModel):
    """Model representing a request for the LLM (Language Model) send into OLS service.

    Attributes:
        query: The query string.
        conversation_id: The optional conversation ID (UUID).
        provider: The optional provider.
        model: The optional model.
        attachments: The optional attachments.
        media_type: The optional parameter for streaming response.

    Example:
        ```python
        llm_request = LLMRequest(query="Tell me about Kubernetes")
        ```
    """

    query: str
    conversation_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    attachments: Optional[list[Attachment]] = None
    media_type: Optional[str] = MEDIA_TYPE_TEXT

    # provides examples for /docs endpoint
    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "query": "write a deployment yaml for the mongodb image",
                    "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                    "provider": "openai",
                    "model": "model-name",
                    "system_prompt": prompts.QUERY_SYSTEM_INSTRUCTION,
                    "attachments": [
                        {
                            "attachment_type": "log",
                            "content_type": "text/plain",
                            "content": "this is attachment",
                        },
                        {
                            "attachment_type": "configuration",
                            "content_type": "application/yaml",
                            "content": "kind: Pod\n metadata:\n    name: private-reg",
                        },
                        {
                            "attachment_type": "configuration",
                            "content_type": "application/yaml",
                            "content": "foo: bar",
                        },
                    ],
                    "media_type": "text/plain",
                }
            ]
        },
    }

    @model_validator(mode="after")
    def validate_provider_and_model(self) -> Self:
        """Perform validation on the provider and model."""
        if self.model and not self.provider:
            raise ValueError(
                "LLM provider must be specified when the model is specified."
            )
        if self.provider and not self.model:
            raise ValueError(
                "LLM model must be specified when the provider is specified."
            )
        if self.media_type not in (MEDIA_TYPE_TEXT, MEDIA_TYPE_JSON):
            raise ValueError(
                f"Invalid media type: '{self.media_type}', must be "
                f"{MEDIA_TYPE_TEXT} or {MEDIA_TYPE_JSON}"
            )
        return self


@dataclass(frozen=True, unsafe_hash=False)
class ReferencedDocument:
    """RAG referenced document.

    Attributes:
    doc_url: URL of the corresponding OCP documentation page
    doc_title: Title of the corresponding OCP documentation page
    """

    doc_url: str
    doc_title: str

    @staticmethod
    def from_rag_chunks(rag_chunks: list["RagChunk"]) -> list["ReferencedDocument"]:
        """Create a list of ReferencedDocument from a list of rag_chunks.

        Order of items is preserved.
        """
        return list(
            OrderedDict(
                (
                    rag_chunk.doc_url,
                    ReferencedDocument(rag_chunk.doc_url, rag_chunk.doc_title),
                )
                for rag_chunk in rag_chunks
            ).values()
        )


class LLMResponse(BaseModel):
    """Model representing a response from the LLM (Language Model).

    Attributes:
        conversation_id: The optional conversation ID (UUID).
        response: The optional response.
        referenced_documents: The optional URLs and titles for the documents used
                              to generate the response.
        truncated: Set to True if conversation history was truncated to be within context window.
        input_tokens: Number of tokens sent to LLM
        output_tokens: Number of tokens received from LLM
        available_quotas: Quota available as measured by all configured quota limiters
    """

    conversation_id: str
    response: str
    referenced_documents: list[ReferencedDocument]
    truncated: bool
    input_tokens: int
    output_tokens: int
    available_quotas: dict[str, int]

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                    "response": "Operator Lifecycle Manager (OLM) helps users install...",
                    "referenced_documents": [
                        {
                            "doc_url": "https://docs.openshift.com/container-platform/4.15/operators/"
                            "understanding/olm/olm-understanding-olm.html",
                            "doc_title": "Operator Lifecycle Manager concepts and resources",
                        },
                    ],
                    "truncated": False,
                    "input_tokens": 123,
                    "output_tokens": 456,
                    "available_quotas": {
                        "UserQuotaLimiter": 998911,
                        "ClusterQuotaLimiter": 998911,
                    },
                }
            ]
        }
    }


class ChatHistoryResponse(BaseModel):
    """Model representing a response to a list conversation request.

    Attributes:
        chat_history: List of conversation messages.
    """

    chat_history: list[BaseMessage]

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "chat_history": [
                        {
                            "content": "what is openshift",
                            "type": "human",
                        },
                        {
                            "content": "OpenShift is a container orchestration platform ...",
                            "type": "ai",
                        },
                    ]
                }
            ]
        }
    }


class ListConversationsResponse(BaseModel):
    """Model representing a response to a request to retrieve a conversation history.

    Attributes:
        conversations: List of conversation IDs, summary and last message timestamp.
    """

    conversations: list[dict[str, Union[str, float]]]

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversations": [
                        {
                            "conversation_id": "15a78660-a18e-447b-9fea-9deb27b63b5f",
                            "topic_summary": "topic1",
                            "last_message_timestamp": 1741268849.345408,
                        },
                        {
                            "conversation_id": "c0a3bc27-77cc-46da-822f-93a9c0e0de4b",
                            "topic_summary": "topic2",
                            "last_message_timestamp": 1741268599.387008,
                        },
                        {
                            "conversation_id": "51984bb1-f3a3-4ab2-9df6-cf92c30bbb7f",
                            "topic_summary": "topic3",
                            "last_message_timestamp": 1741289849.349808,
                        },
                    ]
                }
            ]
        }
    }


class ConversationDeletionResponse(BaseModel):
    """Model representing a response to a conversation deletion request.

    Attributes:
        response: The response of the conversation deletion request.

    Example:
        ```python
        response = ConversationDeletionResponse(response="conversation deleted")
        ```
    """

    response: str

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "response": "conversation deleted",
                }
            ]
        }
    }


class UnauthorizedResponse(BaseModel):
    """Model representing response for missing or invalid credentials."""

    detail: str

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": "Unauthorized: No auth header found",
                },
            ]
        }
    }


class ForbiddenResponse(BaseModel):
    """Model representing response when client does not have permission to access resource."""

    detail: str

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": "Unable to review token",
                },
            ]
        }
    }


class ErrorResponse(BaseModel):
    """Model representing error response for query endpoint."""

    detail: dict[str, str]

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": {
                        "response": "Error while validation question",
                        "cause": "Failed to handle request to https://bam-api.res.ibm.com/v2/text",
                    },
                },
                {
                    "detail": {
                        "response": "Error retrieving conversation history",
                        "cause": "Invalid conversation ID 1237-e89b-12d3-a456-426614174000",
                    },
                },
            ]
        }
    }


class NotAvailableResponse(BaseModel):
    """Model representing error response for readiness endpoint."""

    detail: dict[str, str]

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": {
                        "response": "Service is not ready",
                        "cause": "Index is not ready",
                    }
                },
                {
                    "detail": {
                        "response": "Service is not ready",
                        "cause": "LLM is not ready",
                    },
                },
            ]
        }
    }


class PromptTooLongResponse(ErrorResponse):
    """Model representing error response when prompt is too long."""

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": {
                        "response": "Prompt is too long",
                        "cause": "Prompt length exceeds LLM context window limit (8000 tokens)",
                    },
                },
            ]
        }
    }


class StatusResponse(BaseModel):
    """Model representing a response to a status request.

    Attributes:
        functionality: The functionality of the service.
        status: The status of the service.

    Example:
        ```python
        status_response = StatusResponse(
            functionality="feedback",
            status={"enabled": True},
        )
        ```
    """

    functionality: str
    status: dict

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "functionality": "feedback",
                    "status": {"enabled": True},
                }
            ]
        }
    }


class FeedbackRequest(BaseModel):
    """Model representing a feedback request.

    Attributes:
        conversation_id: The required conversation ID (UUID).
        user_question: The required user question.
        llm_response: The required LLM response.
        sentiment: The optional sentiment.
        user_feedback: The optional user feedback.

    Example:
        ```python
        feedback_request = FeedbackRequest(
            conversation_id="12345678-abcd-0000-0123-456789abcdef",
            user_question="what are you doing?",
            user_feedback="Great service!",
            llm_response="I don't know",
            sentiment=-1,
        )
        ```
    """

    conversation_id: str
    user_question: str
    llm_response: str
    sentiment: Optional[int] = None
    user_feedback: Optional[str] = None

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "12345678-abcd-0000-0123-456789abcdef",
                    "user_question": "foo",
                    "llm_response": "bar",
                    "user_feedback": "Great service!",
                    "sentiment": 1,
                }
            ]
        }
    }

    @field_validator("conversation_id")
    @classmethod
    def check_uuid(cls, value: str) -> str:
        """Check if conversation ID has the proper format."""
        if not suid.check_suid(value):
            raise ValueError(f"Improper conversation ID {value}")
        return value

    @field_validator("sentiment")
    @classmethod
    def check_sentiment(cls, value: Optional[int]) -> Optional[int]:
        """Check if sentiment value is as expected."""
        if value not in {-1, 1, None}:
            raise ValueError(f"Improper value {value}, needs to be -1 or 1")
        return value

    @model_validator(mode="after")
    def check_sentiment_or_user_feedback_set(self) -> Self:
        """Ensure that either 'sentiment' or 'user_feedback' is set."""
        if self.sentiment is None and self.user_feedback is None:
            raise ValueError("Either 'sentiment' or 'user_feedback' must be set")
        return self


class FeedbackResponse(BaseModel):
    """Model representing a response to a feedback request.

    Attributes:
        response: The response of the feedback request.

    Example:
        ```python
        feedback_response = FeedbackResponse(response="feedback received")
        ```
    """

    response: str

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "response": "feedback received",
                }
            ]
        }
    }


class LivenessResponse(BaseModel):
    """Model representing a response to a liveness request.

    Attributes:
        alive: If app is alive.

    Example:
        ```python
        liveness_response = LivenessResponse(alive=True)
        ```
    """

    alive: bool

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "alive": True,
                }
            ]
        }
    }


class ReadinessResponse(BaseModel):
    """Model representing a response to a readiness request.

    Attributes:
        ready: The readiness of the service.
        reason: The reason for the readiness.

    Example:
        ```python
        readiness_response = ReadinessResponse(ready=True, reason="service is ready")
        ```
    """

    ready: bool
    reason: str

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ready": True,
                    "reason": "service is ready",
                }
            ]
        }
    }


class AuthorizationResponse(BaseModel):
    """Model representing a response to an authorization request.

    Attributes:
        user_id: The ID of the logged in user.
        username: The name of the logged in user.
        skip_user_id_check: Skip user_id suid check.
    """

    user_id: str
    username: str
    skip_user_id_check: bool

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "123e4567-e89b-12d3-a456-426614174000",
                    "username": "user1",
                    "skip_user_id_check": False,
                }
            ]
        }
    }


@dataclass
class RagChunk:
    """Model representing a RAG chunk.

    Attributes:
        text: The text used as a RAG chunk.
        doc_url: The URL of the doc from which the RAG chunk comes from.
        doc_title: The title of the doc.
    """

    text: str
    doc_url: str
    doc_title: str


@dataclass
class TokenCounter:
    """Model representing token counter.

    Attributes:
        llm: LLM instance
        input_tokens: number of tokens sent to LLM
        output_tokens: number of tokens received from LLM
        input_tokens_counted: number of input tokens counted by the handler
        llm_calls: number of LLM calls
    """

    llm: Optional[LLM] = None
    input_tokens: int = 0
    output_tokens: int = 0
    input_tokens_counted: int = 0
    llm_calls: int = 0


@dataclass
class SummarizerResponse:
    """Model representing a response from the summarizer.

    Attributes:
        response: The response from the summarizer.
        rag_chunks: The RAG chunks.
        history_truncated: Whether the history was truncated.
        token_counter: Input and output tokens counters.
    """

    response: str
    rag_chunks: list[RagChunk]
    history_truncated: bool
    token_counter: Optional[TokenCounter]


class CacheEntry(BaseModel):
    """Model representing a cache entry.

    Attributes:
        query: The query string.
        response: The response string.
    """

    query: HumanMessage
    response: Optional[AIMessage] = AIMessage("")
    attachments: list[Attachment] = []

    @field_validator("response")
    @classmethod
    def set_none_response_to_empty_string(cls, v: Optional[AIMessage]) -> AIMessage:
        """Convert None response to an empty string."""
        if v is None:
            return AIMessage("")
        return v

    def to_dict(self) -> dict:
        """Convert the cache entry to a dictionary."""
        return {
            "human_query": self.query,
            "ai_response": self.response,
            "attachments": [attachment.model_dump() for attachment in self.attachments],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Create a cache entry from a dictionary."""
        return cls(
            query=data["human_query"],
            response=data["ai_response"],
            attachments=[
                Attachment(**attachment) for attachment in data["attachments"]
            ],
        )

    @staticmethod
    def cache_entries_to_history(
        cache_entries: list["CacheEntry"],
    ) -> list[BaseMessage]:
        """Convert cache entries to a history."""
        history: list[BaseMessage] = []
        for entry in cache_entries:
            entry.query.content = entry.query.content.strip()
            entry.response.content = entry.response.content.strip()
            history.append(entry.query)
            # the real response or empty string when response is not recorded
            history.append(entry.response)

        return history


class MessageEncoder(json.JSONEncoder):
    """Convert Message objects to serializable dictionaries."""

    def default(self, o: Any) -> Union[dict, Any]:
        """Convert a Message object into a serializable dictionary.

        This method is called when an object cannot be serialized by default
        methods. If the object is an instance of HumanMessage or AIMessage,
        it is converted into a dictionary. Otherwise, the default JSONEncoder
        behavior is used.


        Args:
            o: The object to serialize. Expected to be either a HumanMessage
            or AIMessage instance.

        Returns:
            dict: A dictionary containing the message attributes if the input is
                a Message object.
            Any: The result of the parent class's default method for other
                 object types.
        """
        if isinstance(o, (HumanMessage, AIMessage)):
            return {
                "type": o.type,
                "content": o.content,
                "response_metadata": o.response_metadata,
                "additional_kwargs": o.additional_kwargs,
            }
        if isinstance(o, CacheEntry):
            return {
                "__type__": "CacheEntry",
                "query": self.default(o.query),  # Handle nested Message object
                "response": self.default(o.response) if o.response else None,
                "attachments": o.attachments,
            }
        return super().default(o)


class MessageDecoder(json.JSONDecoder):
    """Custom JSON decoder for deserializing Message objects.

    This decoder extends the default JSONDecoder to handle JSON representations of
    HumanMessage and AIMessage objects, converting them back into their respective
    Python objects. It processes JSON objects containing 'type', 'content',
    'response_metadata', and 'additional_kwargs' fields.

    Example:
        >>> decoder = MessageDecoder()
        >>> json.loads('{"type": "human", "content": "Hello", ...}', cls=MessageDecoder)
        HumanMessage(content="Hello", ...)
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the MessageDecoder with custom object hook."""
        super().__init__(object_hook=self._decode_message, *args, **kwargs)

    def _decode_message(
        self, dct: dict[str, Any]
    ) -> Union[HumanMessage, AIMessage, CacheEntry, dict[str, Any]]:
        """Decode JSON dictionary into Message objects if applicable.

        Args:
            dct (dict): Dictionary to decode, potentially representing a Message.

        Returns:
            Union[HumanMessage, AIMessage, dict]: A Message object if the input
            dictionary represents a message, otherwise returns the original dictionary.
        """
        if "__type__" in dct and dct["__type__"] == "CacheEntry":
            # Handle CacheEntry reconstruction
            return CacheEntry(
                query=self._decode_message(dct["query"]),
                response=(
                    self._decode_message(dct["response"]) if dct["response"] else None
                ),
                attachments=dct["attachments"],
            )
        if "type" in dct:
            message: Union[HumanMessage, AIMessage]
            if dct["type"] == "human":
                message = HumanMessage(content=dct["content"])
            elif dct["type"] == "ai":
                message = AIMessage(content=dct["content"])
            else:
                return dct
            message.additional_kwargs = dct["additional_kwargs"]
            message.response_metadata = dct["response_metadata"]
            return message
        return dct


class ProcessedRequest(BaseModel):
    """Model representing processed request w/o LLM response.

    Attributes:
        user_id: The ID of the logged in user.
        conversation_id: Conversation ID.
        query_without_attachments: Query to LLM without attachments.
        previous_input: Previous query to LLM.
        attachments: List of all attachments.
        valid: Whether the query is valid or not.
        timestamps: Timestamps for all operations.
        skip_user_id_check: Flag to skip user ID checking in handler.
        user_token: User token (if provided).
    """

    user_id: str
    conversation_id: str
    query_without_attachments: str
    previous_input: list[CacheEntry]
    attachments: list[Attachment]
    valid: bool
    timestamps: dict[str, float]
    skip_user_id_check: bool
    user_token: str
