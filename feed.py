import requests
import time
import os
from xml.sax.saxutils import escape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# CONFIGURACIÓN DE PLATFORM API
# ==========================================
# Lee el Token de la Platform API desde GitHub Secrets
API_TOKEN = os.environ.get('FOURTHWALL_PLATFORM_TOKEN')

STORE_URL = 'https://opispot.com' 
# Volvemos a la URL maestra (Platform API v1)
BASE_API_URL = 'https://api.fourthwall.com/v1'

session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 429, 500, 502, 503, 504 ])
session.mount('https://', HTTPAdapter(max_retries=retries))

# Autenticación con Bearer Token (Como manda la Platform API)
session.headers.update({
    'Authorization': f'Bearer {API_TOKEN}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
})

# ==========================================
# DICCIONARIO DE PLANTILLAS Y CATEGORÍAS
# ==========================================
# Mapeo de categorías estándar de plantillas de Fourthwall a Google Product Categories
TEMPLATE_CATEGORIES = {
    "apparel": {"gpc": "Apparel & Accessories > Clothing", "is_apparel": True},
    "headwear": {"gpc": "Apparel & Accessories > Clothing Accessories > Hats", "is_apparel": True},
    "drinkware": {"gpc": "Home & Garden > Kitchen & Dining > Tableware > Drinkware", "is_apparel": False},
    "art": {"gpc": "Home & Garden > Decor > Artwork", "is_apparel": False},
    "home": {"gpc": "Home & Garden", "is_apparel": False},
    "accessories": {"gpc": "Apparel & Accessories", "is_apparel": False},
    "stationery": {"gpc": "Office Supplies", "is_apparel": False}
}

CATEGORIA_DEFAULT = {"gpc": "Apparel & Accessories", "is_apparel": True}
# Caché para no consultar la misma plantilla 50 veces y saturar la API
template_cache = {} 

def safe_escape(val):
    if not val: return ""
    if isinstance(val, dict): val = val.get('name', val.get('value', str(val)))
    elif isinstance(val, list): val = ", ".join(str(v) for v in val)
    return escape(str(val))

def extract_price(price_info):
    if isinstance(price_info, dict):
        val = price_info.get('value', '0.00')
        curr = price_info.get('currency', 'USD')
        return f"{val} {curr}"
    return "0.00 USD"

def get_all_products():
    """https://docs.fourthwall.com/api-reference/platform/products/list-products"""
    products = []
    page = 1
    total_pages = 1
    print("📦 Obteniendo catálogo desde Platform API...")
    
    while page <= total_pages:
        url = f"{BASE_API_URL}/products?page={page}&limit=50"
        response = session.get(url)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('data', []) # La Platform API usa 'data', no 'results'
            products.extend(items)
            
            # La Platform API usa un objeto 'pagination'
            pagination = data.get('pagination', {})
            total_pages = pagination.get('total_pages', 1)
            page += 1
        else:
            print(f"❌ Error API: {response.status_code} - {response.text}")
            break
            
    return products

def get_product_details(product_id):
    """https://docs.fourthwall.com/api-reference/platform/products/get-product"""
    url = f"{BASE_API_URL}/products/{product_id}"
    response = session.get(url)
    if response.status_code == 200:
        return response.json().get('data', {})
    return None

def get_template_details(template_id):
    """https://docs.fourthwall.com/api-reference/platform/product-templates/get-product-template"""
    if not template_id:
        return None
        
    if template_id in template_cache:
        return template_cache[template_id]
        
    url = f"{BASE_API_URL}/product-templates/{template_id}"
    response = session.get(url)
    if response.status_code == 200:
        template_data = response.json().get('data', {})
        template_cache[template_id] = template_data
        return template_data
        
    return None

def build_xml_feed():
    base_products = get_all_products()
    if not base_products:
        print("⚠️ No se encontraron productos.")
        return

    xml_items = []
    print(f"🔍 Procesando y categorizando {len(base_products)} productos mediante plantillas...")

    for base_prod in base_products:
        product_id = base_prod.get('id')
        
        # 1. Obtener detalles profundos del producto
        details = get_product_details(product_id)
        if not details: 
            continue
            
        title = details.get('name', 'Producto')
        slug = details.get('slug', '')
        
        # 2. Extraer el template_id y consultar la plantilla oficial
        template_id = details.get('template_id')
        template_data = get_template_details(template_id)
        
        # 3. Categorización estricta basada en la plantilla de Fourthwall
        classification = CATEGORIA_DEFAULT
        if template_data:
            # Generalmente las plantillas tienen un campo 'category', 'group' o similar
            fw_category = str(template_data.get('category', '')).lower()
            
            # Asignamos la taxonomía de Google basándonos en la categoría raíz de la plantilla
            if 'drinkware' in fw_category or 'mug' in fw_category or 'taza' in fw_category:
                classification = TEMPLATE_CATEGORIES["drinkware"]
            elif 'apparel' in fw_category or 'shirt' in fw_category:
                classification = TEMPLATE_CATEGORIES["apparel"]
            elif 'art' in fw_category or 'poster' in fw_category:
                classification = TEMPLATE_CATEGORIES["art"]
            elif 'stationery' in fw_category or 'notebook' in fw_category or 'sticker' in fw_category:
                classification = TEMPLATE_CATEGORIES["stationery"]
            elif 'accessories' in fw_category or 'case' in fw_category:
                classification = TEMPLATE_CATEGORIES["accessories"]

        print(f"✔️ [{title[:30]}...] -> Plantilla ID: {template_id} -> Asignado a: {classification['gpc'].split('>')[-1].strip()}")

        raw_description = details.get('description', '')
        clean_description = raw_description.replace('<p>', '').replace('</p>', '').replace('<br>', ' ').strip()
        product_link = f"{STORE_URL}/products/{slug}"

        raw_images = details.get('images', [])
        all_image_urls = []
        for img in raw_images:
            if isinstance(img, dict) and img.get('url'):
                all_image_urls.append(img.get('url'))

        main_image_link = all_image_urls[0] if all_image_urls else ""
        additional_images = all_image_urls[1:11] 
        image_tags_xml = f"\n            <g:image_link>{safe_escape(main_image_link)}</g:image_link>"
        for add_img in additional_images:
            image_tags_xml += f"\n            <g:additional_image_link>{safe_escape(add_img)}</g:additional_image_link>"

        variants = details.get('variants', [])
        
        # 4. Construcción del XML por variantes
        for variant in variants:
            variant_id = variant.get('id', product_id)
            v_name = variant.get('name', '')
            full_title = f"{title} - {v_name}" if v_name else title
            
            price_str = extract_price(variant.get('price', {}))
            
            attributes = variant.get('attributes', {})
            color = attributes.get('color', attributes.get('Color', ''))
            size = attributes.get('size', attributes.get('Size', ''))

            item_xml = f"""
        <item>
            <g:id>{safe_escape(variant_id)}</g:id>
            <g:item_group_id>{safe_escape(product_id)}</g:item_group_id>
            <g:title>{safe_escape(full_title[:150])}</g:title>
            <g:description>{safe_escape(clean_description[:500])}</g:description>
            <g:link>{safe_escape(f"{product_link}?variant={variant_id}")}</g:link>{image_tags_xml}
            <g:price>{safe_escape(price_str)}</g:price>
            <g:availability>in stock</g:availability>
            <g:condition>new</g:condition>
            <g:google_product_category>{safe_escape(classification['gpc'])}</g:google_product_category>"""
            
            if color: item_xml += f"\n            <g:color>{safe_escape(color)}</g:color>"
            if size: item_xml += f"\n            <g:size>{safe_escape(size)}</g:size>"
            if classification['is_apparel']:
                item_xml += f"\n            <g:gender>unisex</g:gender>\n            <g:age_group>adult</g:age_group>"
            item_xml += "\n        </item>"
            xml_items.append(item_xml)
            
        time.sleep(0.1) # Respetamos límites de la API

    final_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
    <channel>
        <title>Opispot</title>
        <link>{STORE_URL}</link>
        <description>Catálogo oficial de productos para Pinterest</description>
        {''.join(xml_items)}
    </channel>
</rss>"""

    with open('pinterest_feed.xml', 'w', encoding='utf-8') as f:
        f.write(final_xml)
    print(f"✅ Feed XML generado exitosamente con {len(xml_items)} variantes totales.")

if __name__ == "__main__":
    if not API_TOKEN:
        print("❌ Error: Falta la credencial FOURTHWALL_PLATFORM_TOKEN.")
    else:
        build_xml_feed()
