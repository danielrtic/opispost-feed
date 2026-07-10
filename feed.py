import requests
import time
import os
from xml.sax.saxutils import escape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# CONFIGURACIÓN
# ==========================================
API_USER = os.environ.get('FOURTHWALL_API_USER')
API_PASS = os.environ.get('FOURTHWALL_API_PASS')
STORE_URL = 'https://opispot.com' # Recuerda poner tu URL real
BASE_API_URL = 'https://api.fourthwall.com/open-api/v1.0'

session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 429, 500, 502, 503, 504 ])
session.mount('https://', HTTPAdapter(max_retries=retries))

session.auth = (API_USER, API_PASS)
session.headers.update({
    'Content-Type': 'application/json',
    'Accept': 'application/json'
})

def safe_escape(val):
    """
    Función escudo: Convierte diccionarios y listas a texto 
    antes de aplicar el escape XML para evitar cuelgues.
    """
    if not val:
        return ""
    if isinstance(val, dict):
        # Si es un diccionario, intentamos sacar su nombre o valor
        val = val.get('name', val.get('value', str(val)))
    elif isinstance(val, list):
        # Si es una lista, la unimos con comas
        val = ", ".join(str(v) for v in val)
    
    return escape(str(val))

def get_all_products():
    products = []
    page = 1
    total_pages = 1
    print("📦 Obteniendo catálogo completo...")
    
    while page <= total_pages:
        url = f"{BASE_API_URL}/products?page={page}&limit=50"
        print(f"-> Solicitando página {page} de {total_pages}...")
        
        response = session.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            items = data.get('results', [])
            products.extend(items)
            
            print(f"   Se encontraron {len(items)} productos en esta página.")
            
            total_pages = data.get('totalPages', 1)
            page += 1
        else:
            print(f"❌ Error API: {response.status_code}")
            print(f"Detalle: {response.text}")
            break
            
    print(f"✅ Total de productos obtenidos: {len(products)}")
    return products

def categorize_product(title):
    search_string = title.lower()
    category = "Apparel & Accessories"
    gender = "unisex"
    age_group = "adult"
    is_apparel = True 

    if any(word in search_string for word in ['mug', 'taza', 'cup', 'vaso']):
        category = 'Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs'
        is_apparel = False
    elif any(word in search_string for word in ['poster', 'print', 'canvas', 'arte', 'cuadro', 'digital']):
        category = 'Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork'
        is_apparel = False
    
    return {'gpc': category, 'gender': gender if is_apparel else '', 'age_group': age_group if is_apparel else '', 'is_apparel': is_apparel}

def build_xml_feed():
    products = get_all_products()
    if not products:
        print("⚠️ No se encontraron productos.")
        return

    xml_items = []

    for product in products:
        product_id = product.get('id')
        title = product.get('name', 'Producto sin nombre')
        slug = product.get('slug', '')
        
        raw_description = product.get('description', '')
        clean_description = raw_description.replace('<p>', '').replace('</p>', '').replace('<br>', ' ').strip()
        if not clean_description:
            clean_description = title

        product_link = f"{STORE_URL}/products/{slug}"
        classification = categorize_product(title)

        variants = product.get('variants', [])
        
        images = product.get('images', [])
        main_image_link = ''
        if images:
            first_img = images[0]
            if isinstance(first_img, dict):
                main_image_link = first_img.get('url', first_img.get('transformedUrl', ''))
            elif isinstance(first_img, str):
                main_image_link = first_img

        if not variants:
            price_amount = product.get('price', {}).get('value', '0.00')
            price_currency = product.get('price', {}).get('currency', 'USD')
            price_str = f"{price_amount} {price_currency}"

            item_xml = f"""
        <item>
            <g:id>{safe_escape(product_id)}</g:id>
            <g:item_group_id>{safe_escape(product_id)}</g:item_group_id>
            <g:title>{safe_escape(title[:150])}</g:title>
            <g:description>{safe_escape(clean_description[:500])}</g:description>
            <g:link>{safe_escape(product_link)}</g:link>
            <g:image_link>{safe_escape(main_image_link)}</g:image_link>
            <g:price>{safe_escape(price_str)}</g:price>
            <g:availability>in stock</g:availability>
            <g:condition>new</g:condition>
            <g:google_product_category>{safe_escape(classification['gpc'])}</g:google_product_category>"""
            
            if classification['gender']: item_xml += f"\n            <g:gender>{safe_escape(classification['gender'])}</g:gender>"
            if classification['age_group']: item_xml += f"\n            <g:age_group>{safe_escape(classification['age_group'])}</g:age_group>"
            item_xml += "\n        </item>"
            xml_items.append(item_xml)

        else:
            for variant in variants:
                variant_id = variant.get('id', product_id)
                v_name = variant.get('name', '')
                full_title = f"{title} - {v_name}" if v_name else title
                
                v_price = variant.get('price', {})
                price_str = f"{v_price.get('value', '0.00')} {v_price.get('currency', 'USD')}"
                
                attributes = variant.get('attributes', {})
                color = attributes.get('color', '') if classification['is_apparel'] else ''
                size = attributes.get('size', '') if classification['is_apparel'] else ''

                item_xml = f"""
        <item>
            <g:id>{safe_escape(variant_id)}</g:id>
            <g:item_group_id>{safe_escape(product_id)}</g:item_group_id>
            <g:title>{safe_escape(full_title[:150])}</g:title>
            <g:description>{safe_escape(clean_description[:500])}</g:description>
            <g:link>{safe_escape(f"{product_link}?variant={variant_id}")}</g:link>
            <g:image_link>{safe_escape(main_image_link)}</g:image_link>
            <g:price>{safe_escape(price_str)}</g:price>
            <g:availability>in stock</g:availability>
            <g:condition>new</g:condition>
            <g:google_product_category>{safe_escape(classification['gpc'])}</g:google_product_category>"""
                
                if color: item_xml += f"\n            <g:color>{safe_escape(color)}</g:color>"
                if size: item_xml += f"\n            <g:size>{safe_escape(size)}</g:size>"
                if classification['gender']: item_xml += f"\n            <g:gender>{safe_escape(classification['gender'])}</g:gender>"
                if classification['age_group']: item_xml += f"\n            <g:age_group>{safe_escape(classification['age_group'])}</g:age_group>"
                item_xml += "\n        </item>"
                xml_items.append(item_xml)

    final_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
    <channel>
        <title>Mi Tienda Fourthwall</title>
        <link>{STORE_URL}</link>
        <description>Catálogo oficial de productos para Pinterest</description>
        {''.join(xml_items)}
    </channel>
</rss>"""

    with open('pinterest_feed.xml', 'w', encoding='utf-8') as f:
        f.write(final_xml)
    print(f"✅ Feed XML generado exitosamente con {len(xml_items)} items.")

if __name__ == "__main__":
    if not API_USER or not API_PASS:
        print("❌ Error: Faltan las credenciales.")
    else:
        build_xml_feed()
