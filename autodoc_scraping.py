from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = 'https://www.autodoc.co.uk/spares-search?keyword='
chrome_options = Options()
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

def find_in_autodoc(query, supplier = None):
    url = BASE_URL+query
    if supplier:
        url += '&supplier%5B%5D='+supplier
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "listing-title__name"))
    )
    content = driver.page_source
    driver.quit()
    results_dict = get_urls(content)
    return results_dict


def run_autodoc_page_scraper(url: str):
    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.get(url)
    except:
        print('\n\n', url)
        return

    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "product-block__description-title"))
    )
    content = driver.page_source
    scraped_data = get_autodoc_json(content)
        
    scraped_data['url'] = url
    driver.quit()
    return scraped_data
    
def class_to_key(class_part):
    dct = {
        'icon-text--availability': 'availability',
        'icon-text-list': 'other_info',
        'inkl': 'price_including'
    }
    return dct.get(class_part) if class_part in dct.keys() else class_part.lower().replace(' ', '_')

def get_details(detail_block):
    return_info = {}
    details, numbers = detail_block.select('div.product-block__description')[0], detail_block.find_all('div',recursive=False)[-1]
    
    number_details = numbers.select('div.product-block__seo-info-text')[0].text.split(':')[1]
    number_details = {'trade_numbers': list(map(lambda x: x.strip(), number_details.split('\n')))}
    return_info.update(number_details)
    
    product_details = details.select('ul.product-description__list')[0]
    detail_items = {}
    for li_tag in product_details.children:
        if(isinstance(li_tag, Tag)):
            name, value = li_tag.find_all('span', recursive=False)
            name, value = name.text.strip().rstrip(':'), value.text.strip()
            name, value = name.lower().replace('  ', '').replace(' ', '_').replace('_/_', '/'), value.replace('  ', '').replace('\n', ' ')
            detail_items.update({name: value})
    return_info.update(detail_items)
            
    return return_info

def get_pricing(pricing_block):
    return_info = {}
    divs_to_extract = pricing_block.find_all(recursive=False)
    for div in divs_to_extract[:-2]:
        p_tags = div.find_all('p', recursive=False)
        if p_tags:
            text_content = [p.get_text(strip=True) for p in p_tags]
        else:
            text_content = div.get_text(strip=True).replace('  ', '').replace('\n', ' ')
        if 'class' in div.attrs and text_content:
            key = div['class'][-1].split('__')[1]
            key = class_to_key(key)
            return_info[key] = text_content
    
    return return_info

def get_images(images_block):
    images = images_block.find_all('img')
    image_links = [image['src'] for image in images if 'brands' not in image['src']]
    return image_links

def get_compatibility(compatibility_block):
    car_tags = compatibility_block.find_all('div', class_='product-info-block__item')
    cars = [tag.get_text(strip=True) for tag in car_tags]
    return cars

def get_oem(oem_block):
    oem_tags = oem_block.find_all('a', class_='product-oem__link')
    oem_numbers = [tag.get_text(strip=True) for tag in oem_tags]
    return oem_numbers

def get_similar(similar_block):
    items = similar_block.find_all(class_='product-similar-spec__row-link')
    items_structured = [
        {
            "supplier": item.find_all('span')[0].get_text(strip=True),
            "part": item.find_all('span')[1].get_text(strip=True),
            'url': item['href'] if item.name == 'a' else ''
        } for item in items
    ]
    return items_structured

def get_autodoc_json(content):
    soup = BeautifulSoup(content, 'html.parser')
    
    # product section
    product_info = soup.select('section.section.wrap')[0] 
    return_obj = {
        'autodoc_product_code': product_info.findChild('div')['data-article-id']
    }
    
    # heading line
    head_tag = product_info.find('h1')
    return_obj.update({
        'head_name': head_tag.contents[0].strip(),
        'head_description': head_tag.findChildren('span')[1].get_text()
    })
    
    num_info = product_info.select('span.product-block__article')
    for span_tag in num_info:
        inner_data = span_tag.get_text().strip()
        num_name, num_content = inner_data.split(': ')
        return_obj.update({
            num_name.lower().replace(' ', '_'): num_content
        })
        
        
    # detail block
    detail_block = product_info.select('div.col-12.col-lg-4.order-last.order-lg-0')[0]
    product_details = get_details(detail_block)
    return_obj.update(product_details)
    
    # pricing block
    pricing_block = product_info.select('div.col-12.col-md-6.col-lg-4')[1]
    pricing_details = get_pricing(pricing_block)
    return_obj.update(pricing_details)
    
    # compatibility block
    compatibility_block = soup.find('div', id='compatibility')
    if compatibility_block:
        compatibility = get_compatibility(compatibility_block)
        if compatibility:
            return_obj.update({
                'compatibility': compatibility
            })
    
    # OE block
    oem_block = soup.find('div', id='oem')
    if oem_block:
        oem = get_oem(oem_block)
        if oem:
            return_obj.update({
                'oem': oem
            })
        
    images_block = product_info.select('div.product-gallery')[0]
    image_links = get_images(images_block)
    return_obj.update({
        'images': image_links
    })
        
    # similar products
    similar_items_block = soup.find('div', class_='product-similar-spec')
    if similar_items_block:
        similar_items = get_similar(similar_items_block)
        return_obj.update({
            'similar_products': similar_items
        })
    
    
    return return_obj

def get_urls(content):
    content = BeautifulSoup(content, 'html.parser')
    hrefs = {}
    for a_tag in content.select('a.listing-item__name'):
        text_parts = []
        
        if a_tag.contents:
            for child in a_tag.contents:
                if child.name is None and child.strip():
                    text_parts.append(child.strip())
                elif child.name == 'span' and 'highlight' in child.get('class', []):
                    text_parts.append(child.get_text(strip=True))
        
        if text_parts:
            hrefs[' '.join(text_parts)] = a_tag['href']
    
    return hrefs