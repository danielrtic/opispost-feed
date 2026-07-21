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
    "black": "Negro", "dark chocolate": "Marrón Chocolate", "navy": "Azul Marino",
    "true navy": "Azul Marino", "purple": "Morado", "maroon": "Granate",
    "forest green": "Verde Bosque", "heather navy": "Azul Marino Jaspeado",
    "dark heather grey": "Gris Oscuro", "dark heather": "Gris Oscuro",
    "graphite heather": "Gris Grafito", "royal": "Azul Real",
    "military green": "Verde Militar", "charcoal": "Gris Carbón",
    "sapphire": "Azul Zafiro", "heather indigo": "Azul Índigo Jaspeado",
    "heather red": "Rojo Jaspeado", "red": "Rojo", "brick": "Rojo Ladrillo",
    "berry": "Rosa Frambuesa",
    "flo blue": "Azul Eléctrico", "watermelon": "Rosa Sandía",
    "grey": "Gris", "violet": "Violeta", "butter": "Amarillo Pastel",
    "heather royal": "Azul Real Jaspeado", "kelly green": "Verde Esmeralda",
    "heliconia": "Rosa Fucsia", "orange": "Naranja", "tropical blue": "Azul Tropical",
    "irish green": "Verde Vivo", "jade dome": "Verde Jade",
    "heather irish green": "Verde Vivo Jaspeado", "coral silk": "Rosa Coral",
    "sand": "Beige Arena",
    "sport grey": "Gris Jaspeado", "light blue": "Azul Claro",
    "daisy": "Amarillo", "ice grey": "Gris Claro", "white": "Blanco",
    "cornsilk": "Beige", 
    "natural": "Beige Crudo",
    "green": "Verde"
}

# ==========================================
# SUB-CATEGORÍAS Y PRODUCT TYPES
# ==========================================
CATEGORIAS = {
    "hoodie": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "pt": "Ropa Urbana > Sudaderas con Capucha", "is_apparel": True, "is_art": False},
    "sudadera": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "pt": "Ropa Urbana > Sudaderas", "is_apparel": True, "is_art": False},
    "shirt": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "pt": "Ropa Urbana > Camisetas", "is_apparel": True, "is_art": False},
    "camiseta": {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "pt": "Ropa Urbana > Camisetas", "is_apparel": True, "is_art": False},
    "gorra": {"gpc": "Apparel & Accessories > Clothing > Accessories > Hats", "pt": "Accesorios > Gorras", "is_apparel": True, "is_art": False},
    "taza": {"gpc": "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs", "pt": "Hogar > Tazas", "is_apparel": False, "is_art": False},
    "mug": {"gpc": "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs", "pt": "Hogar > Tazas", "is_apparel": False, "is_art": False},
    "poster": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "pt": "Decoración > Pósters", "is_apparel": False, "is_art": True},
    "lienzo": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "pt": "Decoración > Lienzos", "is_apparel": False, "is_art": True},
    "canvas": {"gpc": "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork", "pt": "Decoración > Lienzos", "is_apparel": False, "is_art": True},
    "funda": {"gpc": "Electronics > Electronics Accessories > Computer Components > Computer Accessories > Laptop Accessories > Laptop Cases", "pt": "Accesorios > Fundas", "is_apparel": False, "is_art": False},
    "sticker": {"gpc": "Arts & Entertainment > Hobbies & Creative Arts > Arts & Crafts > Art & Crafting Materials > Embellishments & Trims > Stickers", "pt": "Papelería > Pegatinas", "is_apparel": False, "is_art": False},
    "pegatina": {"gpc": "Arts & Entertainment > Hobbies & Creative Arts > Arts & Crafts > Art & Crafting Materials > Embellishments & Trims > Stickers", "pt": "Papelería > Pegatinas", "is_apparel": False, "is_art": False}
}

CATEGORIA_DEFAULT = {"gpc": "Apparel & Accessories > Clothing > Shirts & Tops", "pt": "Ropa Urbana > Ropa y Accesorios", "is_apparel": True, "is_art": False}

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
    if isinstance(product_state, dict) and product_state.get('type') == 'SOLD_OUT': return 'out of stock'
    if isinstance(variant_stock, dict):
        stock_type = variant_stock.get('type')
        if stock_type == 'UNLIMITED': return 'in stock'
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
    
    # 1. Intentar clasificar por atributos físicos (como Oz para tazas)
    attrs = variant.get('attributes', {})
    size_obj = attrs.get('size', {})
    size_name = str(size_obj.get('name', '')).lower().strip() if isinstance(size_obj, dict) else str(size_obj).lower().strip()
    
    if 'oz' in size_name or 'onza' in size_name: return CATEGORIAS["taza"], "Atributo Oz"
    
    # 2. Buscar palabras clave en el título
    for key, cat_data in CATEGORIAS.items():
        if key in t:
            return cat_data, f"Palabra clave: {key}"
            
    # 3. Fallback genérico por talla de ropa
    if size_name in ['xs', 's', 'm', 'l', 'xl', 'xxl', '2xl', '3xl', '4xl', '5xl']: 
        return CATEGORIAS["shirt"], f"Atributo Talla ({size_name})"
        
    return CATEGORIA_DEFAULT, "Valor por Defecto"

def determinar_genero(title):
    t_lower = title.lower()
    if any(w in t_lower for w in ['mujer', 'chica', 'women', 'ladies', 'crop top', 'vestido', 'falda']): return "female"
    elif any(w in t_lower for w in ['hombre', 'chico', 'men', 'mens']): return "male"
    return "unisex"

def extraer_material_y_patron(title, description, cat_obj):
    text_to_search = (title + " " + description).lower()
    material, pattern = "", ""
    
    # Detección de Material
    if cat_obj['is_apparel']:
        if 'cotton' in text_to_search or 'algodón' in text_to_search or 'algodon' in text_to_search:
            material = "Algodón"
            if 'polyester' in text_to_search or 'poliéster' in text_to_search or 'poliester' in text_to_search:
                material = "Mezcla de Algodón y Poliéster"
        elif 'polyester' in text_to_search or 'poliéster' in text_to_search or 'poliester' in text_to_search:
            material = "Poliéster"
    elif 'taza' in text_to_search or 'mug' in text_to_search or 'ceramic' in text_to_search or 'cerámica' in text_to_search:
        material = "Cerámica"
    elif 'poster' in text_to_search or 'paper' in text_to_search or 'papel' in text_to_search:
        material = "Papel"
    elif 'canvas' in text_to_search or 'lienzo' in text_to_search:
        material = "Lienzo"
        
    # Detección de Patrón / Estampado
    if cat_obj['is_apparel'] or cat_obj.get('pt', '').startswith('Accesorios'):
        if 'bordado' in text_to_search or 'embroidery' in text_to_search or 'stitched' in text_to_search:
            pattern = "Bordado"
        elif 'estampado' in text_to_search or 'print' in text_to_search or 'graphic' in text_to_search or 'dtg' in text_to_search or 'dtfx' in text_to_search:
            pattern = "Estampado Gráfico"
        else:
            pattern = "Estampado"

    return material, pattern

def get_all_products_summary():
    products, page, total_pages = [], 0, 1
    print("📦 Descargando catálogo...")
    while page < total_pages:
        url = f"{BASE_API_URL}/products?page={page}&size=50"
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            items = data.get('results', [])
            if not items: break
            products.extend(items)
            total_pages = data.get('totalPages', 1)
            page += 1
        else: break
    return products

def build_xml_feed():
    summary_products = get_all_products_summary()
    pinterest_items, google_items, bing_items = [], [], []

    for summary in summary_products:
        product_id = summary.get('id')
        title = clean_text(summary.get('name', 'Producto'))
        slug = summary.get('slug', '')
        detailed_product = session.get(f"{BASE_API_URL}/products/{product_id}").json()
        
        if detailed_product.get('access', {}).get('type', 'PUBLIC') != 'PUBLIC': continue

        all_image_urls = [img.get('url') for img in detailed_product.get('images', []) if isinstance(img, dict)]
        if not all_image_urls: continue

        clean_description = clean_text(detailed_product.get('description', '')) or title
        product_link = f"{STORE_URL}/products/{slug}"
        product_state = detailed_product.get('state', {})
        variants = detailed_product.get('variants', [])
        base_price_str = extract_price(detailed_product)

        # Modificamos la función para aceptar imágenes por separado
        def create_xml_item(v_id, v_group_id, v_title, v_link, primary_img, add_imgs, v_price, v_availability, v_cat, v_pt, v_mat=None, v_pat=None, v_color=None, v_size=None, v_sku=None, v_gender=None):
            xml = f"""
        <item>
            <g:id>{safe_escape(v_id)}</g:id>
            <g:item_group_id>{safe_escape(v_group_id)}</g:item_group_id>
            <g:title><![CDATA[{v_title[:150]}]]></g:title>
            <!-- DESC_PLACEHOLDER -->
            <g:link>{safe_escape(v_link)}</g:link>
            <g:image_link>{safe_escape(primary_img)}</g:image_link>"""
            if add_imgs:
                for add_img in add_imgs[:10]:
                    xml += f"\n            <g:additional_image_link>{safe_escape(add_img)}</g:additional_image_link>"
            xml += f"""
            <g:price>{safe_escape(v_price)}</g:price>
            <g:availability>{v_availability}</g:availability>
            <g:condition>new</g:condition>
            <g:brand>Opispot</g:brand>
            <g:identifier_exists>no</g:identifier_exists>
            <g:google_product_category><![CDATA[{v_cat}]]></g:google_product_category>
            <g:product_type><![CDATA[{v_pt}]]></g:product_type>"""
            if v_color: xml += f"\n            <g:color><![CDATA[{v_color}]]></g:color>"
            if v_size: xml += f"\n            <g:size><![CDATA[{v_size}]]></g:size>"
            if v_mat: xml += f"\n            <g:material><![CDATA[{v_mat}]]></g:material>"
            if v_pat: xml += f"\n            <g:pattern><![CDATA[{v_pat}]]></g:pattern>"
            if v_gender: xml += f"\n            <g:gender>{v_gender}</g:gender>\n            <g:age_group>adult</g:age_group>"
            if v_sku: xml += f"\n            <g:mpn>{safe_escape(v_sku)}</g:mpn>"
            xml += "\n        </item>"
            return xml

        if not variants:
            cat_obj, _ = clasificar_producto({}, title)
            gender = determinar_genero(title) if cat_obj['is_apparel'] else None
            mat, pat = extraer_material_y_patron(title, clean_description, cat_obj)
            
            # --- NUEVA GENERACIÓN DE TÍTULOS SEO (SIN VARIANTES) ---
            marca = "Opispot"
            if cat_obj['is_apparel']:
                genero_txt = "Unisex" if gender == "unisex" else ("Hombre" if gender == "male" else "Mujer")
                tipo_prenda = cat_obj['pt'].split(" > ")[-1]
                if tipo_prenda.endswith('s'): tipo_prenda = tipo_prenda[:-1] 
                seo_title = f"{marca} {tipo_prenda} {genero_txt} | {title}"
            elif cat_obj['is_art']:
                seo_title = f"{marca} Póster | {title}"
            else:
                seo_title = f"{marca} | {title}"
            # -------------------------------------------------------------
            
            desc_unica = f"{seo_title}. Diseño original de la marca independiente Opispot. Detalles: {clean_description}"
            
            # Lógica de imágenes (Producto sin variantes)
            pin_main = all_image_urls[0]
            pin_adds = [img for img in all_image_urls if img != pin_main]
            
            gb_main = all_image_urls[2] if len(all_image_urls) > 2 else all_image_urls[0]
            gb_adds = [img for img in all_image_urls if img != gb_main]
            
            # Generamos XML específico para Pinterest
            xml_pin = create_xml_item(product_id, product_id, seo_title, product_link, pin_main, pin_adds, base_price_str, extract_availability(product_state, {}), cat_obj['gpc'], cat_obj['pt'], v_mat=mat, v_pat=pat, v_gender=gender)
            pinterest_items.append(xml_pin.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{desc_unica[:500]}]]></g:description>"))
            
            # Generamos XML específico para Google y Bing
            xml_gb = create_xml_item(product_id, product_id, seo_title, product_link, gb_main, gb_adds, base_price_str, extract_availability(product_state, {}), cat_obj['gpc'], cat_obj['pt'], v_mat=mat, v_pat=pat, v_gender=gender)
            google_items.append(xml_gb.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{desc_unica[:5000]}]]></g:description>"))
            
            bing_base = remove_accents(xml_gb)
            bing_desc = remove_accents(desc_unica[:10000])
            bing_items.append(bing_base.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{bing_desc}]]></g:description>"))
        
        else:
            for variant in variants:
                v_id = variant.get('id', product_id)
                v_name = clean_text(variant.get('name', ''))
                v_name_clean = re.sub(re.escape(title), '', v_name, flags=re.IGNORECASE).strip(' -')
                cat_obj, _ = clasificar_producto(variant, title)
                
                color_raw = variant.get('attributes', {}).get('color', {}).get('name', '')
                color_es = COLORES_ESPANOL.get(color_raw.lower(), color_raw)
                sku = variant.get('sku', '')
                
                gender = determinar_genero(f"{title} {v_name_clean}") if cat_obj['is_apparel'] else None
                mat, pat = extraer_material_y_patron(title, clean_description, cat_obj)
                
                # --- NUEVA GENERACIÓN DE TÍTULOS SEO (CON VARIANTES) ---
                marca = "Opispot"
                talla = variant.get('attributes',{}).get('size',{}).get('name')
                
                if cat_obj['is_apparel']:
                    genero_txt = "Unisex" if gender == "unisex" else ("Hombre" if gender == "male" else "Mujer")
                    tipo_prenda = cat_obj['pt'].split(" > ")[-1]
                    if tipo_prenda.endswith('s'): tipo_prenda = tipo_prenda[:-1] 
                    full_title = f"{marca} {tipo_prenda} {genero_txt} | {title}"
                elif cat_obj['is_art']:
                    full_title = f"{marca} Póster | {title}"
                else:
                    full_title = f"{marca} | {title}"
                
                if color_es:
                    full_title += f" - Color {color_es}"
                if talla:
                    full_title += f" - Talla {talla}"
                # -------------------------------------------------------------
                
                desc_unica = f"{full_title}. Diseño original de la marca independiente Opispot. Detalles: {clean_description}"
                
                # Lógica de imágenes (Producto con variantes)
                v_images = [img.get('url') for img in variant.get('images', [])] or all_image_urls
                
                pin_main = variant.get('thumbnailImage', {}).get('url') or v_images[0]
                pin_adds = [img for img in v_images if img != pin_main]
                
                gb_main = v_images[2] if len(v_images) > 2 else v_images[0]
                gb_adds = [img for img in v_images if img != gb_main]
                
                # Generamos XML específico para Pinterest
                xml_pin = create_xml_item(v_id, product_id, full_title, f"{product_link}?variant={v_id}", pin_main, pin_adds, extract_price(variant), extract_availability(product_state, variant.get('stock')), cat_obj['gpc'], cat_obj['pt'], v_mat=mat, v_pat=pat, v_color=color_es, v_size=talla, v_sku=sku, v_gender=gender)
                pinterest_items.append(xml_pin.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{desc_unica[:500]}]]></g:description>"))
                
                # Generamos XML específico para Google y Bing
                xml_gb = create_xml_item(v_id, product_id, full_title, f"{product_link}?variant={v_id}", gb_main, gb_adds, extract_price(variant), extract_availability(product_state, variant.get('stock')), cat_obj['gpc'], cat_obj['pt'], v_mat=mat, v_pat=pat, v_color=color_es, v_size=talla, v_sku=sku, v_gender=gender)
                google_items.append(xml_gb.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{desc_unica[:5000]}]]></g:description>"))
                
                bing_base = remove_accents(xml_gb)
                bing_desc = remove_accents(desc_unica[:10000])
                bing_items.append(bing_base.replace("<!-- DESC_PLACEHOLDER -->", f"<g:description><![CDATA[{bing_desc}]]></g:description>"))
        
        print(f"✔️ {title[:30]}... procesado")

    # Guardado final
    def write_feed(filename, items_list):
        with open(filename, 'w', encoding='utf-8-sig') as f:
            f.write(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel><title>Opispot</title><link>{STORE_URL}</link>{"".join(items_list)}</channel></rss>')

    write_feed('pinterest_feed.xml', pinterest_items)
    write_feed('google_feed.xml', google_items)
    write_feed('bing_feed.xml', bing_items)
    print("✅ Feeds generados con éxito: Títulos SEO optimizados y estrategias de imagen separadas.")

if __name__ == "__main__":
    if not API_USER or not API_PASS: print("❌ Credenciales faltantes")
    else: build_xml_feed()
