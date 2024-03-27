from time import gmtime, strftime
from autodoc_scraping import find_in_autodoc, run_autodoc_page_scraper
from onlinecarparts_scraping import find_in_onlinecarparts, run_onlinecarparts_page_scraper
import requests

SUPPLIERS = {
    "motorad": '10706',
    "mahle": '10223'
}
WEBSITE_SCRAPERS = {
    'autodoc': {
        'page': run_autodoc_page_scraper,
        'query': find_in_autodoc
    },
    'autoteiledirekt': {
        'page': run_onlinecarparts_page_scraper,
        'query': find_in_onlinecarparts
    }
}

class SearchQuery:
    def __init__(self,
                query: str,
                webhook_url: str = None,
                is_page: bool = False,
                depth: int = 2,
                supplier: str = "motorad",
                query_id: str = None,
                website: str = "autodoc" # or autoteiledirect
                ):
        self.query = query
        self.webhook_url = webhook_url
        self.is_page = is_page
        self.depth = depth
        self.supplier = supplier
        self.query_id = query_id
        self.website = website

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



# Process the request
def get_content(input: SearchQuery):
    depth = input.depth
    print("\n\n", "STARTING DEPTH", depth, "\n\n")
    items_list = []
    items_tree = dict()
    
    # website scraper validation
    website = input.website        
    scraping_functions = WEBSITE_SCRAPERS.get(website)
    if not scraping_functions:
        return None
    function_to_scrape_page = scraping_functions['page']
    function_to_scrape_query = scraping_functions['query']
    
    # Get page result. Check if the input query is not url, get page url
    if input.is_page:
        scraped_data = function_to_scrape_page(input.query)
    else:
        supplier_code = SUPPLIERS[input.supplier]
        results_dict = function_to_scrape_query(input.query, supplier = supplier_code)
        if not results_dict:
            return {"content": "No results found"}
        url = list(results_dict.values())[0]
        scraped_data = function_to_scrape_page(url)
        
    # Get info about similar items
    similars = scraped_data.get('similar_products')
    
    if website == "autodoc":
        if similars:
            urls = [item['url'] for item in similars if item['url']]
        else:
            return {"content": "No similars found"}

        similar_keys = [url.split('/')[-1] for url in urls]

        # key - product code for this item, update items_tree and items_list for current item
        key = scraped_data['website_product_code']
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
                new_items = get_content(req_obj)
                if new_items.get('content') == "No results found": continue
                items_list.extend(new_items['items'])
                items_tree.update(new_items['tree'])
                new_key = url.split('/')[-1]
                if items_tree.get(key) and new_key in items_tree.values():
                    items_tree[key][new_key] = new_items['tree'][new_key]
    
        # Prepare results, send to the webhook or return for recursion case
        return_obj =  {
                'info':{
                    'website': website,
                    'depth': depth,
                    'total': len(set([item['website_product_code'] for item in items_list])),
                    'time': get_time(),
                    'supplier': None if input.is_page else input.supplier
                },
                'tree': items_tree if input.is_page else {key: build_tree(key, items_tree, depth+1)},
                'items': items_list
            }
    else:
        key = scraped_data['website_product_code']
        items_list.append(scraped_data)
        
        return_obj =  {
                'info':{
                    'website': website,
                    'depth': "Not available for " + website,
                    'total': len(set([item['website_product_code'] for item in items_list])),
                    'time': get_time(),
                    'supplier': None if input.is_page else input.supplier
                },
                'tree': "Not available for " + website,
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