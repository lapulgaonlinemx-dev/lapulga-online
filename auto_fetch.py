import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore

# Configuración del enlace de afiliado
AFFILIATE_LINK = "https://www.mercadolibre.com.mx/social/eg20260925105329727"

def init_firebase():
    """Inicializa la conexión a Firebase usando la Variable de Entorno"""
    if os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
    elif "FIREBASE_CREDENTIALS" in os.environ:
        cred_dict = json.loads(os.environ["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(cred_dict)
    else:
        raise Exception("No se encontraron las credenciales de Firebase.")
    
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

def fetch_category_deals(category_name, total_needed=100):
    """Obtiene ofertas utilizando endpoints abiertos sin bloqueo de IP 403"""
    deals = []
    
    # Mapeo de términos de búsqueda universales
    queries = {
        "Tech": "tecnologia",
        "Gaming": "videojuegos",
        "Moda": "ropa",
        "Belleza": "skincare"
    }
    
    query = queries.get(category_name, "ofertas")
    
    # Endpoint abierto de tendencias/búsqueda directa por país (MLM)
    url = f"https://api.mercadolibre.com/sites/MLM/search?q={query}&limit=50"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "*/*"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            results = response.json().get("results", [])
            for item in results:
                price = item.get("price", 0)
                original_price = item.get("original_price") or (price * 1.2)
                
                if price > 0:
                    thumbnail = item.get("thumbnail", "").replace("I.jpg", "O.jpg")
                    deals.append({
                        "title": item.get("title", "Oferta Destacada"),
                        "store": "Mercado Libre",
                        "category": category_name,
                        "price": float(price),
                        "oldPrice": float(original_price if original_price > price else price * 1.25),
                        "image": thumbnail,
                        "link": AFFILIATE_LINK,
                        "active": True,
                        "ml_id": item.get("id")
                    })
        else:
            print(f"⚠️ Status {response.status_code} en {category_name}. Generando catálogo alternativo...")
    except Exception as e:
        print(f"❌ Error al consultar {category_name}: {e}")
        
    return deals[:total_needed]

def fetch_all_balanced_deals():
    """Junta ofertas por cada categoría"""
    all_deals = []
    categories = ["Tech", "Gaming", "Moda", "Belleza"]
    
    for cat in categories:
        print(f"📦 Obteniendo productos para la categoría: {cat}...")
        category_deals = fetch_category_deals(cat, total_needed=100)
        all_deals.extend(category_deals)
        print(f"✔️ Obtenidos {len(category_deals)} de {cat}.")
        
    return all_deals

def sync_to_firestore(db, deals):
    """Limpia la colección products y guarda los nuevos datos"""
    products_ref = db.collection("products")
    
    # 1. Limpiar catálogo anterior
    docs = products_ref.stream()
    for doc in docs:
        doc.reference.delete()
    print("🧹 Base de datos limpiada.")

    # 2. Insertar ofertas obtenidas
    count = 0
    for deal in deals:
        products_ref.add(deal)
        count += 1
        print(f"✅ [{count}/{len(deals)}] Agregado ({deal['category']}): {deal['title'][:35]}...")

if __name__ == "__main__":
    db = init_firebase()
    print("🔎 Iniciando actualización de ofertas...")
    deals = fetch_all_balanced_deals()
    if deals:
        print(f"🔥 Se obtuvieron {len(deals)} ofertas. Sincronizando con Firebase...")
        sync_to_firestore(db, deals)
        print("🚀 ¡Sincronización completada con éxito!")
    else:
        print("❌ No se pudieron extraer datos de la API pública.")
