class CleanHostMiddleware:
    """
    Sanitize HTTP_HOST to prevent DisallowedHost errors when
    behind proxies like Cloudflare that may append duplicate hosts.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.META.get("HTTP_HOST", "")
        if "," in host:
            # Take only the first host before any comma
            request.META["HTTP_HOST"] = host.split(",")[0].strip()
        return self.get_response(request)
