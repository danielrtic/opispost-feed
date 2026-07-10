import requests
import time
import os
import json
from xml.sax.saxutils import escape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# CONFIGURACIÓN
# ==========================================
API_USER = os.environ.get('FOURTHWALL_API_USER')
API_PASS = os.environ.get('FOURTHWALL_API_PASS')
STORE_URL = 'https://opispot.com' 
BASE_API_URL = 'https://api.fourthwall.com/open-api/v1.0'

session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 429, 500, 502, 503, 504 ])
session.mount('https://', HTTPAdapter(max_retries=retries))
session.auth = (API_USER, API_PASS)
session.headers.update({
    'Content-Type': 'application/json',
    'Accept': 'application/json'
})

CATEGORIAS_FOURTHWALL = {
    "shirt": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "is_apparel": True},
    "mug": {"gpc": "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs", "is_apparel": False},
    "sticker": {"gpc": "Arts & Entertainment > Hobbies & Creative Arts > Arts & Crafts > Art & Crafting Materials > Embellishments & Trims > Stickers", "is_apparel": False},
    "notebook": {"gpc": "Office Supplies > Office Instruments > Notebooks & Notepads", "is_apparel": False},
    "poster": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "is_apparel": False},
    "laptop case": {"gpc": "Electronics > Electronics Accessories > Computer Components > Computer Accessories > Laptop Accessories > Laptop Cases", "is_apparel": False}
}

CATEGORIA_DEFAULT = {"gpc": "Apparel & Accessories", "is_apparel": True} 

def safe_escape(val):
    if not val: return ""
    if isinstance(val, dict): val = val.get('name', val.get('value', str(val)))
    elif isinstance(val, list): val = ", ".join(str(v) for v in val)
    return escape(str(val))

def extract_price(data_dict):
    price_obj = data_dict.get('price') or data_dict.get('unitPrice') or data_dict.get('retailPrice')
    if isinstance(price_obj, dict):
        val = price_obj.get('value', price_obj.get('amount', '0.00'))
        curr = price_obj.get('currency', price_obj.get('currencyCode', 'USD'))
        return f"{val} {curr}"
    elif isinstance(price_obj, (int, float, str)) and price_obj:
        return f"{price_obj} USD"
    return "0.00 USD"

def get_all_products_summary():
    products = []
    page = 1
    total_pages = 1
    print("📦 Obteniendo lista base de productos...")
    
    while page <= total_pages:
        url = f"{BASE_API_URL}/products?page={page}&limit=50"
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            items = data.get('results', [])
            products.extend(items)
            total_pages = data.get('totalPages', 1)
            page += 1
        else:
            print(f"❌ Error API: {response.status_code}")
            break
    return products

def get_product_details(product_id, is_first=False):
    url = f"{BASE_API_URL}/products/{product_id}"
    response = session.get(url)
    if response.status_code == 200:
        data = response.json()
        data = data.get('data', data) # Extrae la data pura
        
        # MODO FORENSE: Imprime el primer producto al 100% en consola
        if is_first:
            print("\n" + "="*60)
            print("🕵️ MODO FORENSE: JSON PURO DEL PRIMER PRODUCTO DESDE LA API")
            print("Revisa esto para confirmar que Fourthwall NO envía la plantilla:")
            print("="*60)
            print(json.dumps(data, indent=2))
            print("="*60 + "\n")
            
        return data
    return None

def get_exact_classification(detailed_product):
    """
    Clasificación estricta: NO usa el título.
    Usa metadatos ocultos (si existen) o datos físicos empíricos de las variantes.
    """
    # 1. Búsqueda de metadatos profundos (Por si Fourthwall los activa algún día)
    fields_to_check = []
    if detailed_product.get('productType'): fields_to_check.append(str(detailed_product.get('productType')).lower())
    if detailed_product.get('type'): fields_to_check.append(str(detailed_product.get('type')).lower())
    
    for field in fields_to_check:
        for key, data in CATEGORIAS_FOURTHWALL.items():
            if key in field: return data, f"Metadato: {field}"

    # 2. Búsqueda Estricta por Atributos Físicos (NO adivinanza)
    variants = detailed_product.get('variants', [])
    for variant in variants:
        attrs = variant.get('attributes', {})
        for attr_key, attr_val in attrs.items():
            val_str = str(attr_val).lower()
            
            # Es una taza si su capacidad se mide en onzas
            if 'oz' in val_str: 
                return CATEGORIAS_FOURTHWALL["mug"], "Atributo Físico (Capacidad Oz)"
                
            # Es ropa si usa tallaje textil estandarizado
            if val_str in ['s', 'm', 'l', 'xl', '2xl', '3xl', '4xl']: 
                return CATEGORIAS_FOURTHWALL["shirt"], "Atributo Físico (Tallaje Textil)"
                
            # Son pósters/lienzos si usan medidas por pulgadas/cm (ej. 18x24)
            if 'x' in val_str and ('"' in val_str or 'inch' in val_str or 'cm' in val_str):
                return CATEGORIAS_FOURTHWALL["poster"], "Atributo Físico (Dimensiones de Arte)"

    # 3. Clasificación base segura
    return CATEGORIA_DEFAULT, None

def build_xml_feed():
    summary_products = get_all_products_summary()
    if not summary_products:
        print("⚠️ No se encontraron productos.")
        return

    xml_items = []
    print(f"🔍 Iniciando Deep Fetch para {len(summary_products)} productos...")

    is_first_product = True

    for summary in summary_products:
        product_id = summary.get('id')
        title = summary.get('name', 'Producto sin nombre')
        slug = summary.get('slug', '')
        
        detailed_product = get_product_details(product_id, is_first=is_first_product)
        is_first_product = False # Solo imprime el primero
        
        if not detailed_product: detailed_product = summary
        time.sleep(0.1)

        classification, matched_term = get_exact_classification(detailed_product)
        
        if matched_term:
            print(f"✔️ [{title[:30]}...] -> Identificado por {matched_term} -> {classification['gpc'].split('>')[-1].strip()}")
        else:
            print(f"⚠️ [{title[:30]}...] -> Sin atributos físicos claros. Default: Ropa.")

        raw_description = detailed_product.get('description', summary.get('description', ''))
        clean_description = raw_description.replace('<p>', '').replace('</p>', '').replace('<br>', ' ').strip()
        if not clean_description: clean_description = title
        product_link = f"{STORE_URL}/products/{slug}"

        raw_images = detailed_product.get('images', summary.get('images', []))
        all_image_urls = []
        for img in raw_images:
            img_url = img.get('url', img.get('transformedUrl', '')) if isinstance(img, dict) else img if isinstance(img, str) else ""
            if img_url and img_url not in all_image_urls:
                all_image_urls.append(img_url)

        main_image_link = all_image_urls[0] if all_image_urls else ""
        additional_images = all_image_urls[1:11] 

        image_tags_xml = f"\n            <g:image_link>{safe_escape(main_image_link)}</g:image_link>"
        for add_img in additional_images:
            image_tags_xml += f"\n            <g:additional_image_link>{safe_escape(add_img)}</g:additional_image_link>"

        base_price_str = extract_price(detailed_product)
        variants = detailed_product.get('variants', summary.get('variants', []))

        if not variants:
            item_xml = f"""
        <item>
            <g:id>{safe_escape(product_id)}</g:id>
            <g:item_group_id>{safe_escape(product_id)}</g:item_group_id>
            <g:title>{safe_escape(title[:150])}</g:title>
            <g:description>{safe_escape(clean_description[:500])}</g:description>
            <g:link>{safe_escape(product_link)}</g:link>{image_tags_xml}
            <g:price>{safe_escape(base_price_str)}</g:price>
            <g:availability>in stock</g:availability>
            <g:condition>new</g:condition>
            <g:google_product_category>{safe_escape(classification['gpc'])}</g:google_product_category>"""
            
            if classification['is_apparel']:
                item_xml += f"\n            <g:gender>unisex</g:gender>\n            <g:age_group>adult</g:age_group>"
            item_xml += "\n        </item>"
            xml_items.append(item_xml)
        else:
            for variant in variants:
                variant_id = variant.get('id', product_id)
                v_name = variant.get('name', '')
                full_title = f"{title} - {v_name}" if v_name else title
                
                variant_price_str = extract_price(variant)
                if variant_price_str == "0.00 USD": variant_price_str = base_price_str
                
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
            <g:price>{safe_escape(variant_price_str)}</g:price>
            <g:availability>in stock</g:availability>
            <g:condition>new</g:condition>
            <g:google_product_category>{safe_escape(classification['gpc'])}</g:google_product_category>"""
                
                if color: item_xml += f"\n            <g:color>{safe_escape(color)}</g:color>"
                if size: item_xml += f"\n            <g:size>{safe_escape(size)}</g:size>"
                if classification['is_apparel']:
                    item_xml += f"\n            <g:gender>unisex</g:gender>\n            <g:age_group>adult</g:age_group>"
                item_xml += "\n        </item>"
                xml_items.append(item_xml)

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
    if not API_USER or not API_PASS:
        print("❌ Error: Faltan las credenciales.")
    else:
        build_xml_feed()
