import requests
import time
import os
from xml.sax.saxutils import escape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# CONFIGURACIÓN (Open API - Basic Auth)
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

CATEGORIAS = {
    "apparel": {"gpc": "Apparel & Accessories > Clothing", "is_apparel": True},
    "drinkware": {"gpc": "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs", "is_apparel": False},
    "art": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "is_apparel": False},
    "stationery": {"gpc": "Office Supplies > Office Instruments > Notebooks & Notepads", "is_apparel": False},
    "sticker": {"gpc": "Arts & Entertainment > Hobbies & Creative Arts > Arts & Crafts > Art & Crafting Materials > Embellishments & Trims > Stickers", "is_apparel": False}
}

CATEGORIA_DEFAULT = {"gpc": "Apparel & Accessories", "is_apparel": True}

def safe_escape(val):
    if not val: return ""
    if isinstance(val, dict): val = val.get('name', val.get('value', str(val)))
    elif isinstance(val, list): val = ", ".join(str(v) for v in val)
    return escape(str(val))

def extract_price(price_info):
    if isinstance(price_info, dict):
        val = price_info.get('value', price_info.get('amount', '0.00'))
        curr = price_info.get('currency', price_info.get('currencyCode', 'USD'))
        return f"{val} {curr}"
    return "0.00 USD"

def clasificar_producto(detailed_product, title):
    """Filtro Híbrido Súper Ampliado para Open API"""
    
    # 1. Filtro Físico Ampliado (Tallas completas, onzas, medidas)
    variants = detailed_product.get('variants', [])
    for variant in variants:
        attrs = variant.get('attributes', {})
        for _, attr_val in attrs.items():
            val_str = str(attr_val).lower().strip()
            
            if 'oz' in val_str or 'onza' in val_str: 
                return CATEGORIAS["drinkware"], f"Atributo: {val_str}"
            if val_str in ['xs', 's', 'm', 'l', 'xl', 'xxl', '2xl', '3xl', '4xl', 'small', 'medium', 'large', 'x-large', 'extra large']: 
                return CATEGORIAS["apparel"], f"Atributo: {val_str}"
            if 'x' in val_str and ('"' in val_str or 'cm' in val_str or 'inch' in val_str or 'in' in val_str): 
                return CATEGORIAS["art"], f"Atributo: {val_str}"

    # 2. Respaldo por Título (Imprescindible si la API oculta datos)
    title_lower = title.lower()
    if any(w in title_lower for w in ['taza', 'mug', 'vaso']): return CATEGORIAS["drinkware"], "Título (Taza/Mug)"
    if any(w in title_lower for w in ['sticker', 'pegatina']): return CATEGORIAS["sticker"], "Título (Sticker)"
    if any(w in title_lower for w in ['libreta', 'notebook', 'cuaderno']): return CATEGORIAS["stationery"], "Título (Libreta)"
    if any(w in title_lower for w in ['poster', 'print', 'lienzo', 'digital', 'cuadro']): return CATEGORIAS["art"], "Título (Arte)"
    if any(w in title_lower for w in ['camiseta', 'shirt', 'hoodie', 'sudadera', 'gorra']): return CATEGORIAS["apparel"], "Título (Ropa)"

    return CATEGORIA_DEFAULT, "Valor por Defecto"

def get_all_products_summary():
    """Descarga de productos con Paginación Infinita y Segura"""
    products = []
    page = 1
    has_more = True
    print("📦 Conectando a Open API y descargando catálogo completo...")
    
    while has_more:
        # Aumentamos el limit a 100 para reducir el número de llamadas (Fourthwall lo suele permitir)
        url = f"{BASE_API_URL}/products?page={page}&limit=100"
        print(f"-> Descargando página {page}...")
        
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            items = data.get('results', data.get('data', []))
            
            # Si la página devuelve un array vacío, hemos llegado al final real de la tienda
            if not items:
                print("   [Fin del catálogo alcanzado]")
                has_more = False
                break
                
            products.extend(items)
            print(f"   + {len(items)} productos base encontrados.")
            page += 1
        else:
            print(f"❌ Error API listando productos en la página {page}: {response.status_code} - {response.text}")
            break
            
    return products

def build_xml_feed():
    summary_products = get_all_products_summary()
    if not summary_products:
        print("⚠️ No se encontraron productos.")
        return

    xml_items = []
    print(f"\n🔍 Procesando y enriqueciendo {len(summary_products)} productos base encontrados...")

    for summary in summary_products:
        product_id = summary.get('id')
        title = summary.get('name', 'Producto sin nombre')
        slug = summary.get('slug', '')
        
        url_detail = f"{BASE_API_URL}/products/{product_id}"
        resp_detail = session.get(url_detail)
        detailed_product = resp_detail.json().get('data', summary) if resp_detail.status_code == 200 else summary
            
        classification, razon = clasificar_producto(detailed_product, title)
        print(f"{'✔️' if 'Defecto' not in razon else '⚠️'} [{title[:25]}...] -> {razon} -> {classification['gpc'].split('>')[-1].strip()}")

        raw_description = detailed_product.get('description', '')
        clean_description = raw_description.replace('<p>', '').replace('</p>', '').replace('<br>', ' ').strip()
        if not clean_description: clean_description = title
        product_link = f"{STORE_URL}/products/{slug}"

        raw_images = detailed_product.get('images', [])
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

        base_price_str = extract_price(detailed_product.get('price', summary.get('price')))
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
            <g:brand>Opispot</g:brand>
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
                
                variant_price_str = extract_price(variant.get('price'))
                if variant_price_str == "0.00 USD": variant_price_str = base_price_str
                
                attributes = variant.get('attributes', {})
                color = attributes.get('color', attributes.get('Color', ''))
                size = attributes.get('size', attributes.get('Size', ''))
                
                # Extracción extra (SKU y Peso)
                sku = variant.get('sku', '')
                weight = variant.get('weight', {})
                weight_str = f"{weight.get('value')} {weight.get('unit', 'g')}" if isinstance(weight, dict) and weight.get('value') else ""

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
            <g:brand>Opispot</g:brand>
            <g:google_product_category>{safe_escape(classification['gpc'])}</g:google_product_category>"""
                
                if color: item_xml += f"\n            <g:color>{safe_escape(color)}</g:color>"
                if size: item_xml += f"\n            <g:size>{safe_escape(size)}</g:size>"
                if sku: item_xml += f"\n            <g:mpn>{safe_escape(sku)}</g:mpn>"
                if weight_str: item_xml += f"\n            <g:shipping_weight>{safe_escape(weight_str)}</g:shipping_weight>"
                
                if classification['is_apparel']:
                    item_xml += f"\n            <g:gender>unisex</g:gender>\n            <g:age_group>adult</g:age_group>"
                item_xml += "\n        </item>"
                xml_items.append(item_xml)
            
        time.sleep(0.05)

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
