import azure.functions as func
import logging
import json
import create_response

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route()
def find_parts(req: func.HttpRequest) -> func.HttpResponse:
    request_data = req.get_json()
    logging.info(request_data)

    input = create_response.SearchQuery(
        query = request_data.get('query'),
        webhook_url = request_data.get('webhook_url'),
        is_page = request_data.get('is_page') or False,
        depth = request_data.get('depth') or 2,
        supplier = request_data.get('supplier') or 'motorad',
        query_id = request_data.get('query_id'),
        website = request_data.get('website') or "autodoc"
    )
    
    results = create_response.get_content(input)
    if not results:
        return func.HttpResponse(
            "Can't handle. Check request correction",
            status_code=404
        )
        
    return func.HttpResponse(
            json.dumps(results),
            status_code=200
        )