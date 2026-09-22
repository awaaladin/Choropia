from rest_framework.pagination import CursorPagination, PageNumberPagination


class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class FeedCursorPagination(CursorPagination):
    """Used for feed/chat-message endpoints where stable ordering under inserts matters more
    than jumping to arbitrary pages."""

    page_size = 20
    ordering = "-created_at"
    page_size_query_param = "page_size"
    max_page_size = 100
