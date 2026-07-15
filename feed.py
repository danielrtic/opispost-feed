import requests
import time
import os
import html
import re
import unicodedata
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

# ==========================================
# TRADUCCIÓN DE COLORES PARA SEO EN ESPAÑOL
# ==========================================
COLORES_ESPANOL = {
    "black": "Negro",
    "dark chocolate": "Marrón Chocolate",
    "navy": "Azul Marino",
    "true navy": "Azul Marino",
    "purple": "Morado",
    "maroon": "Granate",
    "forest green": "Verde Bosque",
    "heather navy": "Azul Marino Jaspeado",
    "dark heather grey": "Gris Oscuro",
    "dark heather": "Gris Oscuro",
    "graphite heather": "Gris Grafito",
    "royal": "Azul Real",
    "military green": "Verde Militar",
    "charcoal": "Gris Carbón",
    "sapphire": "Azul Zafiro",
    "heather indigo": "Índigo Jaspeado",
    "heather red": "Rojo Jaspeado",
    "red": "Rojo",
    "brick": "Rojo Ladrillo",
    "berry": "Frambuesa",
    "flo blue": "Azul Eléctrico",
    "watermelon": "Rosa Sandía",
    "grey": "Gris",
    "violet": "Violeta",
    "butter": "Amarillo Pastel",
    "heather royal": "Azul Real Jaspeado",
    "kelly green": "Verde Esmeralda",
    "heliconia": "Rosa Fucsia",
    "orange": "Naranja",
    "tropical blue": "Azul Tropical",
    "irish green": "Verde Vivo",
    "jade dome": "Verde Jade",
    "heather irish green": "Verde Vivo Jaspeado",
    "coral silk": "Color Coral",
    "sand": "Color Arena",
    "sport grey": "Gris Jaspeado",
    "light blue": "Azul Claro",
    "daisy": "Amarillo",
    "ice grey": "Gris Claro",
    "white": "Blanco",
    "cornsilk": "Beige",
    "natural": "Crudo / Natural"
}

CATEGORIAS = {
    "apparel": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "is_apparel": True, "is_art": False},
    "drinkware": {"gpc": "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs", "is_apparel": False, "is_art": False},
    "art": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "is_apparel": False, "is_art": True},
    "stationery": {"gpc": "Office Supplies > Office Instruments > Notebooks & Notepads", "is_apparel": False, "is_art": False},
    "sticker": {"gpc": "Arts & Entertainment > Hobbies & Creative Arts > Arts & Crafts > Art & Crafting Materials > Embellishments & Trims > Stickers", "is_apparel": False, "is_art": False},
    "accessories": {"gpc": "Electronics > Electronics Accessories > Computer Components > Computer Accessories > Laptop Accessories > Laptop Cases", "is_apparel": False, "is_art": False}
}

CATEGORIA_DEFAULT = {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "is_apparel": True, "is_art": False}

def safe_escape(val):
    if not val: return ""
    if isinstance(val, dict): val = val.get('name', val.get('value', str(val)))
    elif isinstance(val, list): val = ", ".join(str(v) for v in val)
    return escape(str(val))

def clean_text(text):
    if not text: return ""
    text = html.unescape(str(text))
    text = html.unescape(text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'<[^>]+>', ' ', text)
    
    text = re.sub(r'[\u2600-\u27BF]', '', text)
    text = re.sub(r'[\U00010000-\U0010FFFF]', '', text)
    
    text = text.replace("Copy of ", "").replace("Copy of", "")
    return " ".join(text.split()).strip()

def remove_accents(text):
    if not text: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(text)) if unicodedata.category(c) != 'Mn')

def extract_availability(product_state, variant_stock):
    if isinstance(product_state, dict) and product_state.get('type') == 'SOLD_OUT':
        return 'out of stock'
    if isinstance(variant_stock, dict):
        stock_type = variant_stock.get('type')
        if stock_type == 'UNLIMITED': 
            return 'in stock'
        if stock_type == 'LIMITED':
            return 'in stock' if variant_stock.get('inStock', 0) > 0 else 'out of stock'
    return 'in stock'

def extract_price(data_dict):
    if not data_dict or not isinstance(data_dict, dict): return "0.00 USD"
    price_obj = data_dict.get('unitPrice') or data_dict.get('price')
    if isinstance(price_obj, dict):
        val = price_obj.get('value', price_obj.get('amount', '0.00'))
        curr = price_obj.get('currency', price_obj.get('currencyCode', 'USD'))
        return f"{val} {curr}"
    return "0.00 USD"

def clasificar_producto(variant, title):
    t = title.lower()
    if any(w in t for w in ['sticker', 'pegatina']): return CATEGORIAS["sticker"], "Título (Sticker)"
    if any(w in t for w in ['taza', 'mug', 'vaso']): return CATEGORIAS["drinkware"], "Título (Taza/Mug)"
    if any(w in t for w in ['libreta', 'notebook', 'cuaderno']): return CATEGORIAS["stationery"], "Título (Libreta)"
    if any(w in t for w in ['funda', 'case', 'sleeve', 'fundas para portátil']): return CATEGORIAS["accessories"], "Título (Accesorio)"
    if any(w in t for w in ['poster', 'print', 'lienzo', 'cuadro', 'canvas']): return CATEGORIAS["art"], "Título (Arte)"
    if any(w in t for w in ['camiseta', 'shirt', 'hoodie', 'sudadera', 'gorra', 'ropa', 'top', 'vestido']): return CATEGORIAS["apparel"], "Título (Ropa)"

    attrs = variant.get('attributes', {})
    size_obj = attrs.get('size', {})
    size_name = str(size_obj.get('name', '')).lower().strip() if isinstance(size_obj, dict) else str(size_obj).lower().strip()
            
    if size_name:
        if 'oz' in size_name or 'onza' in size_name: return CATEGORIAS["drinkware"], f"Atributo Talla ({size_name})"
        if size_name in ['xs', 's', 'm', 'l', 'xl', 'xxl', '2xl', '3xl', '4xl', '5xl', 'small', 'medium', 'large']: return CATEGORIAS["apparel"], f"Atributo Talla ({size_name})"
        if 'x' in size_name and any(m in size_name for m in ['"', 'cm', 'in', 'mm']): return CATEGORIAS["art"], f"Atributo Medida ({size_name})"

    return CATEGORIA_DEFAULT, "Valor por Defecto"

def determinar_genero(title):
    t_lower = title.lower()
    if any(w in t_lower for w in ['mujer', 'chica', 'women', 'ladies', 'crop top', 'vestido', 'falda']):
        return "female"
    elif any(w in t_lower for w in ['hombre', 'chico', 'men', 'mens']):
        return "male"
    return "unisex"

def get_all_products_summary():
    products = []
    page = 0 
    total_pages = 1
    print("📦 Conectando a Open API y descargando catálogo completo...")
    
    while page < total_pages:
        url = f"{BASE_API_URL}/products?page={page}&size=50"
        print(f"-> Descargando página {page}...")
        
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            items = data.get('results', [])
            if not items: break
            products.extend(items)
            print(f"   + {len(items)} productos base encontrados.")
            total_pages = data.get('totalPages', 1)
            page += 1
        else:
            print(f"❌ Error API listando productos: {response.status_code}")
            break
            
    return products

def build_xml_feed():
    summary_products = get_all_products_summary()
    if not summary_products:
        print("⚠️ No se encontraron productos.")
        return

    pinterest_items = []
    google_items = []
    bing_items = []
    
    print(f"\n🔍 Procesando {len(summary_products)} productos base (Limpiando HTML y aplicando SEO Español)...")

    for summary in summary_products:
        product_id = summary.get('id')
        raw_title = summary.get('name', 'Producto sin nombre')
        title = clean_text(raw_title)
        slug = summary.get('slug', '')
        
        url_detail = f"{BASE_API_URL}/products/{product_id}"
        resp_detail = session.get(url_detail)
        detailed_product = resp_detail.json() if resp_detail.status_code == 200 else summary

        access_info = detailed_product.get('access', {})
        access_type = access_info.get('type', 'PUBLIC') if isinstance(access_info, dict) else 'PUBLIC'
        
        if access_type != 'PUBLIC':
            continue

        raw_images = detailed_product.get('images', [])
        all_image_urls = []
        for img in raw_images:
            img_url = img.get('url', '') if isinstance(img, dict) else img if isinstance(img, str) else ""
            if img_url and img_url not in all_image_urls: all_image_urls.append(img_url)

        if not all_image_urls:
            continue

        raw_description = detailed_product.get('description', '')
        clean_description = clean_text(raw_description)
        if not clean_description: clean_description = title
        
        product_link = f"{STORE_URL}/products/{slug}"
        product_state = detailed_product.get('state', {})
        variants = detailed_product.get('variants', [])
        base_price_str = extract_price(detailed_product)

        # ==========================================
        # PRODUCTOS SIN VARIANTES
        # ==========================================
        if not variants:
            classification, razon = clasificar_producto({}, title)
            main_image_link = all_image_urls[0] if all_image_urls else ""
            gender = determinar_genero(title) if classification['is_apparel'] else None
            
            # --- INYECCIÓN SEO BASE ---
            prefijo_seo = ""
            if classification['is_apparel']:
                genero_txt = "Unisex" if gender == "unisex" else ("Hombre" if gender == "male" else "Mujer")
                prefijo_seo = f"Ropa Urbana {genero_txt} - "
            elif classification['is_art']:
                prefijo_seo = "Póster Decorativo - "
                
            seo_title = f"{prefijo_seo}{title}"
            # --------------------------
            
            item_xml_base = f"""
        <item>
            <g:id>{safe_escape(product_id)}</g:id>
            <g:item_group_id>{safe_escape(product_id)}</g:item_group_id>
            <g:title><![CDATA[{seo_title[:150]}]]></g:title>
            <!-- DESC_PLACEHOLDER -->
            <g:link>{safe_escape(product_link)}</g:link>
            <g:image_link>{safe_escape(main_image_link)}</g:image_link>"""
            
            for add_img in all_image_urls[1:11]:
                item_xml_base += f"\n            <g:additional_image_link>{safe_escape(add_img)}</g:additional_image_link>"

            item_xml_base += f"""
            <g:price>{safe_escape(base_price_str)}</g:price>
            <g:availability>{extract_availability(product_state, {})}</g:availability>
            <g:condition>new</g:condition>
            <g:brand>Opispot</g:brand>
            <g:identifier_exists>no</g:identifier_exists>
            <g:google_product_category><![CDATA[{classification['gpc']}]]></g:google_product_category>"""
            
            if gender:
                item_xml_base += f"\n            <g:gender>{gender}</g:gender>\n            <g:age_group>adult</g:age_group>"
            item_xml_base += "\n        </item>"
            
            pinterest_items.append(item_xml_base.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{clean_description[:500]}]]></g:description>"))
            google_items.append(item_xml_base.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{clean_description[:5000]}]]></g:description>"))
            
            bing_base = remove_accents(item_xml_base)
            bing_desc = remove_accents(clean_description[:10000])
            bing_items.append(bing_base.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{bing_desc}]]></g:description>"))
            
        # ==========================================
        # PRODUCTOS CON VARIANTES
        # ==========================================
        else:
            for variant in variants:
                variant_id = variant.get('id', product_id)
                raw_v_name = variant.get('name', '')
                
                # --- INYECCIÓN SEO PARA VARIANTES ---
                attributes = variant.get('attributes', {})
                color_name = ""
                color_obj = attributes.get('color')
                if isinstance(color_obj, dict): color_name = color_obj.get('name', '')
                
                size_name = ""
                size_obj = attributes.get('size')
                if isinstance(size_obj, dict): size_name = size_obj.get('name', '')

                classification, razon = clasificar_producto(variant, title)
                
                v_name = clean_text(raw_v_name)
                v_name_clean = re.sub(re.escape(title), '', v_name, flags=re.IGNORECASE).strip(' -')
                
                temp_title = f"{title} - {v_name_clean}" if v_name_clean else title
                gender = determinar_genero(temp_title) if classification['is_apparel'] else None

                prefijo_seo = ""
                if classification['is_apparel']:
                    genero_txt = "Unisex" if gender == "unisex" else ("Hombre" if gender == "male" else "Mujer")
                    prefijo_seo = f"Ropa Urbana {genero_txt} - "
                elif classification['is_art']:
                    prefijo_seo = "Póster Decorativo - "

                color_espanol = COLORES_ESPANOL.get(color_name.lower(), color_name) if color_name else ""

                if color_espanol:
                    full_title = f"{prefijo_seo}{title} Color {color_espanol}"
                    if v_name_clean and color_name.lower() not in v_name_clean.lower():
                         full_title += f" - {v_name_clean}"
                else:
                    full_title = f"{prefijo_seo}{title} - {v_name_clean}" if v_name_clean else f"{prefijo_seo}{title}"
                # ------------------------------------
                
                variant_price_str = extract_price(variant)
                if variant_price_str == "0.00 USD": variant_price_str = base_price_str
                
                availability = extract_availability(product_state, variant.get('stock'))
                
                sku = variant.get('sku', '')
                weight = variant.get('weight', {})
                weight_str = f"{weight.get('value')} {weight.get('unit', 'g')}" if isinstance(weight, dict) and weight.get('value') else ""

                raw_var_images = variant.get('images', [])
                var_image_urls = []
                for img in raw_var_images:
                    img_url = img.get('url', '') if isinstance(img, dict) else img if isinstance(img, str) else ""
                    if img_url and img_url not in var_image_urls: var_image_urls.append(img_url)

                var_thumb = variant.get('thumbnailImage', {})
                main_image_link = var_thumb.get('url') if isinstance(var_thumb, dict) and var_thumb.get('url') else ""
                
                if not main_image_link:
                    main_image_link = var_image_urls[0] if var_image_urls else (all_image_urls[0] if all_image_urls else "")
                
                images_to_use = var_image_urls if var_image_urls else all_image_urls

                item_xml_base = f"""
        <item>
            <g:id>{safe_escape(variant_id)}</g:id>
            <g:item_group_id>{safe_escape(product_id)}</g:item_group_id>
            <g:title><![CDATA[{full_title[:150]}]]></g:title>
            <!-- DESC_PLACEHOLDER -->
            <g:link>{safe_escape(f"{product_link}?variant={variant_id}")}</g:link>
            <g:image_link>{safe_escape(main_image_link)}</g:image_link>"""
                
                for add_img in images_to_use[:11]:
                    if add_img != main_image_link: 
                        item_xml_base += f"\n            <g:additional_image_link>{safe_escape(add_img)}</g:additional_image_link>"

                item_xml_base += f"""
            <g:price>{safe_escape(variant_price_str)}</g:price>
            <g:availability>{availability}</g:availability>
            <g:condition>new</g:condition>
            <g:brand>Opispot</g:brand>
            <g:identifier_exists>no</g:identifier_exists>
            <g:google_product_category><![CDATA[{classification['gpc']}]]></g:google_product_category>"""
                
                if color_espanol: item_xml_base += f"\n            <g:color><![CDATA[{color_espanol}]]></g:color>"
                if size_name: item_xml_base += f"\n            <g:size><![CDATA[{size_name}]]></g:size>"
                if sku: item_xml_base += f"\n            <g:mpn>{safe_escape(sku)}</g:mpn>"
                if weight_str: item_xml_base += f"\n            <g:shipping_weight>{safe_escape(weight_str)}</g:shipping_weight>"
                
                if gender:
                    item_xml_base += f"\n            <g:gender>{gender}</g:gender>\n            <g:age_group>adult</g:age_group>"
                item_xml_base += "\n        </item>"
                
                pinterest_items.append(item_xml_base.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{clean_description[:500]}]]></g:description>"))
                google_items.append(item_xml_base.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{clean_description[:5000]}]]></g:description>"))
                
                bing_base = remove_accents(item_xml_base)
                bing_desc = remove_accents(clean_description[:10000])
                bing_items.append(bing_base.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{bing_desc}]]></g:description>"))
                
            print(f"✔️ [{title[:35]}...] -> Procesado con SEO")
            
        time.sleep(0.05)

    def write_feed(filename, items_list):
        final_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
    <channel>
        <title>Opispot</title>
        <link>{STORE_URL}</link>
        <description>Catálogo oficial de productos</description>
        {''.join(items_list)}
    </channel>
</rss>"""
        with open(filename, 'w', encoding='utf-8-sig') as f:
            f.write(final_xml)

    write_feed('pinterest_feed.xml', pinterest_items)
    write_feed('google_feed.xml', google_items)
    write_feed('bing_feed.xml', bing_items)
    
    print(f"✅ Feeds generados exitosamente. Títulos SEO y colores en español aplicados.")

if __name__ == "__main__":
    if not API_USER or not API_PASS:
        print("❌ Error: Faltan las credenciales.")
    else:
        build_xml_feed()
