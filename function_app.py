import azure.functions as func
import logging

import json
from autodoc_scraping import find_in_autodoc, run_autodoc_page_scraper
# from onlinecarparts_scraping import find_in_onlinecarparts, run_onlinecarparts_page_scraper
from time import gmtime, strftime
import requests
suppliers = {
    "motorad": '10706',
    "mahle": '10223'
}
class SearchQuery:
    def __init__(self,
                query: str,
                webhook_url: str = None,
                is_page: bool = False,
                depth: int = 2,
                supplier: str = "motorad",
                query_id: str = None
                ):
        self.query = query
        self.webhook_url = webhook_url
        self.is_page = is_page
        self.depth = depth
        self.supplier = supplier
        self.query_id = query_id



app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="get-content-autodoc/")
def ScrapeWebsites(req: func.HttpRequest) -> func.HttpResponse:
    logging.info(req.get_json())

    
    input = SearchQuery(
        query = req.get_json().get('query'),
        webhook_url = req.get_json().get('webhook_url'),
        is_page = req.get_json().get('is_page'),
        depth = req.get_json().get('depth') or 2,
        supplier = req.get_json().get('supplier') or 'motorad',
        query_id = req.get_json().get('query_id'),
    )
    return json.dumps(get_content_autodoc(input))
    # name = req.params.get('name')
    # if not name:
    #     try:
    #         req_body = req.get_json()
    #     except ValueError:
    #         pass
    #     else:
    #         name = req_body.get('name')

    # if name:
    #     return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    # else:
    #     return func.HttpResponse(
    #          "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
    #          status_code=200
    #     )
        
        
        
        
        
# Process the request
def get_content_autodoc(input: SearchQuery):
    depth = input.depth
    print("\n\n", "STARTING DEPTH", depth, "\n\n")
    items_list = []
    items_tree = dict()
    
    # Get page result. Check if the input query is not url, get page url
    if input.is_page:
        scraped_data = run_autodoc_page_scraper(input.query)
    else:
        supplier_code = suppliers[input.supplier]
        results_dict = find_in_autodoc(input.query, supplier = supplier_code)
        if not results_dict:
            return {"content": "No results found"}
        url = list(results_dict.values())[0]
        scraped_data = run_autodoc_page_scraper(url)
        
    # Get info about similar items
    similars = scraped_data.get('similar_products')
    if similars:
        urls = [item['url'] for item in similars if item['url']]
    else:
        return {"content": "No results found"}
    
    similar_keys = [url.split('/')[-1] for url in urls]
    
    # key - product code for this item, update items_tree and items_list for current item
    key = scraped_data['autodoc_product_code']
    items_tree.update({
            key: {
                similar_key: None
                for similar_key in similar_keys}
        })
    items_list.append(scraped_data)
    
    # Check the depth for limit the recursion, scrape all possible similar items
    if depth > 1:
        print("\n\n", "Start scraping similars for depth", depth, "...\n\n")
        for url in urls:
            req_obj = SearchQuery
            req_obj.query = url
            req_obj.is_page = True
            req_obj.depth = depth -1
            new_items = get_content_autodoc(req_obj)
            if new_items.get('content') == "No results found": continue
            items_list.extend(new_items['items'])
            items_tree.update(new_items['tree'])
            new_key = url.split('/')[-1]
            if items_tree.get(key) and new_key in items_tree.values():
                items_tree[key][new_key] = new_items['tree'][new_key]
                
    
    # Prepare results, send to the webhook or return for recursion case
    return_obj =  {
            'info':{
                'depth': depth,
                'total': len(set([item['autodoc_product_code'] for item in items_list])),
                'time': get_time(),
                'supplier': None if input.is_page else input.supplier
            },
            'tree': items_tree if input.is_page else {key: build_tree(key, items_tree, depth+1)},
            'items': items_list
        }
    
    print("\n\n", "Done for depth", depth, "\n\n")
    if input.is_page:
        return return_obj
    else:
        return_obj.update({
            'query_id': input.query_id
        })
        if input.webhook_url:
            requests.post(input.webhook_url, json=return_obj)
        else:
            return return_obj
        
        
        
        
        
        
        
        
        
# Build a tree from raw tree list
def build_tree(node, tree_dict, max_depth, depth = 0, visited=None):
    if visited is None:
        visited = set()
    if depth == max_depth or node in visited:
        return {}
    
    if node not in tree_dict:
        return None
    
    visited.add(node)
    
    subtree = {child: build_tree(child, tree_dict, max_depth, depth+1, visited.copy()) for child in tree_dict[node]}
    return subtree

# Current time in gmt
def get_time():
    formatted_time = strftime("%d.%m.%y/%H:%M:%S", gmtime())
    return formatted_time